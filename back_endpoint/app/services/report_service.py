"""风险审核报告：生成（幂等）与查询。"""

import json
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import AuthUser
from app.core.errors import not_found
from app.models import (
    ApprovalOpinion,
    ApprovalTask,
    Attachment,
    Document,
    DocumentItem,
    Report,
    RiskAnalysis,
    RiskEvidence,
    RiskItem,
    RiskRule,
    User,
    Vendor,
)
from app.services import ai_client, log_service
from app.services.serializers import (
    LEVEL_TO_API,
    document_out,
    evidence_out,
    money,
    report_out,
    risk_item_out,
)
from app.utils.ids import next_report_no
from app.utils.timefmt import fmt_dt, now

LEVEL_TEXT = {"high": "高风险", "mid": "中风险", "low": "低风险", "none": "无风险"}
SUGGESTION_TEXT = {
    "high": "存在高风险项，建议财务人工复核后再决定通过或退回。",
    "mid": "存在中风险项，建议补充材料并说明后再审批。",
    "low": "仅存在低风险提示，可按常规流程审批。",
    "none": "未发现明显风险，建议通过。",
}
RECOMMENDATION_LABELS = {
    "pass": "建议通过",
    "supplement": "补充材料",
    "manual_review": "人工复核",
    "reject_suggest": "建议驳回",
}
ACTION_TEXT = {
    "pass": "建议通过",
    "supplement": "补充材料",
    "manual_review": "人工复核",
    "reject_suggest": "建议驳回",
}


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _amount_text(value) -> str:
    try:
        return f"¥{Decimal(str(value)):,.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return "¥0.00"


def _clean_basis(text: str) -> str:
    return str(text or "").strip().rstrip("。；;，, ")


def get_by_doc(db: Session, doc_id: int) -> Report | None:
    return db.execute(
        select(Report).where(Report.document_id == doc_id).order_by(Report.id.desc()).limit(1)
    ).scalar_one_or_none()


def _parsed_total(db: Session, doc_id: int) -> Decimal | None:
    rows = db.execute(
        select(Attachment).where(Attachment.document_id == doc_id)
    ).scalars().all()
    if not rows:
        return None
    from app.models import AttachmentParseResult

    results = db.execute(
        select(AttachmentParseResult).where(
            AttachmentParseResult.attachment_id.in_([att.id for att in rows])
        )
    ).scalars().all()
    total = Decimal("0.00")
    found = False
    for result in results:
        if not isinstance(result.result_json, list):
            continue
        for field in result.result_json:
            if not isinstance(field, dict) or field.get("label") != "金额合计":
                continue
            raw = str(field.get("value", "")).replace("¥", "").replace("￥", "").replace(",", "").strip()
            try:
                total += Decimal(raw)
                found = True
            except Exception:
                continue
    return total if found else None


def _amount_checks(db: Session, doc: Document) -> list[dict]:
    items = db.execute(
        select(DocumentItem).where(DocumentItem.document_id == doc.id).order_by(DocumentItem.item_no)
    ).scalars().all()
    groups: dict[str, Decimal] = {}
    for item in items:
        groups[item.expense_type] = groups.get(item.expense_type, Decimal("0.00")) + item.amount
    checks = [
        {
            "name": name,
            "doc_amount": money(amount),
            "parsed_amount": money(amount),
            "diff": 0.0,
            "conclusion": "一致",
        }
        for name, amount in groups.items()
    ]
    total = sum((item.amount for item in items), Decimal("0.00"))
    parsed = _parsed_total(db, doc.id)
    if parsed is None:
        parsed = total
    diff = parsed - total
    checks.append(
        {
            "name": "合计",
            "doc_amount": money(total),
            "parsed_amount": money(parsed),
            "diff": money(diff),
            "conclusion": "一致" if abs(diff) <= Decimal("0.01") else "不一致",
            "is_total": True,
        }
    )
    return checks


def _risk_blocks(db: Session, analysis: RiskAnalysis | None) -> tuple[list[dict], list[dict]]:
    if not analysis:
        return [], []
    rows = db.execute(
        select(RiskItem, RiskRule)
        .join(RiskRule, RiskRule.id == RiskItem.rule_id)
        .where(RiskItem.analysis_id == analysis.id)
        .order_by(RiskItem.id)
    ).all()
    evidences = db.execute(
        select(RiskEvidence)
        .where(RiskEvidence.risk_item_id.in_([item.id for item, _ in rows]))
        .order_by(RiskEvidence.id)
    ).scalars().all() if rows else []
    evidence_by_item: dict[int, list[RiskEvidence]] = {}
    for evidence in evidences:
        evidence_by_item.setdefault(evidence.risk_item_id, []).append(evidence)

    risk_items = [
        {
            "rule_code": rule.rule_code,
            "title": rule.rule_name,
            "level": LEVEL_TO_API.get(item.risk_level, item.risk_level),
            "basis": item.risk_desc,
            "status": item.status,
        }
        for item, rule in rows
    ]
    evidence_rows = [
        {
            "rule_code": next((rule.rule_code for item, rule in rows if item.id == evidence.risk_item_id), ""),
            "snippet": evidence.evidence_content or "",
            "source": evidence.source or "",
        }
        for evidence in evidences
    ]
    return risk_items, evidence_rows


def _vendor_block(db: Session, doc: Document) -> dict | None:
    if doc.doc_type not in ("采购付款", "合同付款"):
        return None
    text = " ".join(filter(None, [doc.project, doc.description]))
    vendor = db.execute(select(Vendor).order_by(Vendor.id)).scalars().all()
    matched = next((row for row in vendor if row.name and row.name in text), None)
    if not matched:
        return None
    return {
        "name": matched.name,
        "score": matched.score,
        "level": LEVEL_TO_API.get(matched.risk_level, matched.risk_level),
        "note": matched.note or "",
        "blacklist": bool(matched.blacklist),
    }


def _reviews(db: Session, doc: Document) -> list[dict]:
    rows = db.execute(
        select(ApprovalOpinion, User.real_name, ApprovalTask.node_name)
        .join(ApprovalTask, ApprovalTask.id == ApprovalOpinion.task_id)
        .outerjoin(User, User.id == ApprovalOpinion.create_by)
        .where(
            ApprovalTask.document_id == doc.id,
            ApprovalOpinion.action.in_(("approve", "return", "reject")),
        )
        .order_by(ApprovalOpinion.id)
    ).all()
    return [
        {
            "name": name or "系统",
            "role": node or "审批人",
            "avatar": (name or "系")[:1],
            "content": opinion.opinion,
            "created_at": fmt_dt(opinion.create_time),
        }
        for opinion, name, node in rows
    ]


def _normalize_recommendation(level: str, recommendation: str | None) -> str:
    if recommendation not in RECOMMENDATION_LABELS:
        recommendation = {"high": "manual_review", "mid": "supplement"}.get(level, "pass")
    if level == "high" and recommendation not in ("manual_review", "reject_suggest"):
        return "manual_review"
    if level == "mid" and recommendation == "pass":
        return "supplement"
    if level in ("low", "none") and recommendation in ("manual_review", "reject_suggest"):
        return "pass"
    return recommendation


def _fallback_report_text(
    doc: Document,
    level: str,
    risk_items: list[dict],
    recommendation: str,
) -> tuple[str, str]:
    level_text = LEVEL_TEXT.get(level, "无风险")
    amount_text = _amount_text(doc.total_amount)
    if risk_items:
        details = "；".join(
            f"{item['rule_code']} {item['title']}（{LEVEL_TEXT.get(item['level'], item['level'])}）："
            f"{_clean_basis(item['basis'])}"
            for item in risk_items[:3]
        )
        summary = (
            f"单据《{doc.title}》（{doc.doc_no}）为{doc.doc_type}，金额 {amount_text}，"
            f"共触发 {len(risk_items)} 项风险：{details}。整体风险等级为{level_text}。"
        )
    else:
        summary = (
            f"单据《{doc.title}》（{doc.doc_no}）为{doc.doc_type}，金额 {amount_text}。"
            "经规则引擎与主体语义校验，未发现明显风险，整体风险等级为无风险。"
        )

    top = "；".join(_clean_basis(item["basis"]) for item in risk_items[:2])
    if recommendation == "manual_review":
        suggestion = (
            f"发现高风险项：{top}。建议【人工复核】，请申请人补充说明并提交相关佐证材料。"
            if top
            else "存在高风险项，建议【人工复核】后再决定通过或退回。"
        )
    elif recommendation == "reject_suggest":
        suggestion = (
            f"风险项较严重：{top}。建议【建议驳回】，请财务复核后与申请人沟通处理。"
            if top
            else "风险项较严重，建议【建议驳回】并留存核查记录。"
        )
    elif recommendation == "supplement":
        suggestion = (
            f"发现中风险项：{top}。建议【补充材料】，请申请人说明情况并补充凭证后重新提交。"
            if top
            else "存在中风险项，建议【补充材料】并说明后再审批。"
        )
    else:
        suggestion = (
            f"仅存在低风险提示：{top}。建议按常规流程通过，审批人知悉即可。"
            if top
            else "未发现明显风险，建议按常规流程通过。"
        )
    return _clip(summary, 300), _clip(suggestion, 300)


def _ai_report_text(
    doc: Document,
    applicant_name: str,
    level: str,
    risk_items: list[dict],
    recommendation: str,
    amount_checks: list[dict],
) -> tuple[str, str, str] | None:
    """调用大模型生成“人话”摘要与处理建议；失败返回 None 由模板兜底。"""
    if not ai_client.is_ai_enabled():
        return None
    context = {
        "单据": {
            "编号": doc.doc_no,
            "标题": doc.title,
            "类型": doc.doc_type,
            "申请人": applicant_name,
            "部门": doc.department or "",
            "项目": doc.project or "",
            "总金额": _amount_text(doc.total_amount),
        },
        "整体风险": LEVEL_TEXT.get(level, "无风险"),
        "金额核对": amount_checks,
        "风险项": [
            {
                "规则": item["rule_code"],
                "名称": item["title"],
                "等级": LEVEL_TEXT.get(item["level"], item["level"]),
                "判断依据": item["basis"],
            }
            for item in risk_items
        ],
        "规则引擎建议": ACTION_TEXT.get(recommendation, "建议通过"),
    }
    prompt = (
        "你是财务风控审核报告撰写专家。请根据以下审核数据生成报告摘要与处理建议。\n"
        "要求：\n"
        "1. summary 不超过 300 字，语气专业、客观，说明单据信息、金额、主要风险及整体结论；\n"
        "2. suggestion 不超过 150 字，必须解释建议依据，并用【】标出处理动作；\n"
        "3. recommendation 只能是 pass / supplement / manual_review / reject_suggest 之一；\n"
        "4. 不要编造数据，只使用给定信息。\n"
        f"审核数据：{json.dumps(context, ensure_ascii=False)}\n"
        '返回严格 JSON：{"summary": "...", "suggestion": "...", "recommendation": "..."}'
    )
    payload = ai_client.chat_json(
        [
            {"role": "system", "content": "你是严谨的财务风控审核报告撰写专家，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=800,
    )
    if not isinstance(payload, dict):
        return None
    summary = str(payload.get("summary") or "").strip()
    suggestion = str(payload.get("suggestion") or "").strip()
    if not summary or not suggestion:
        return None
    ai_recommendation = str(payload.get("recommendation") or "").strip()
    if ai_recommendation not in RECOMMENDATION_LABELS:
        ai_recommendation = recommendation
    return _clip(summary, 300), _clip(suggestion, 300), ai_recommendation


def _compose_report_text(
    doc: Document,
    applicant_name: str,
    level: str,
    risk_items: list[dict],
    recommendation: str,
    amount_checks: list[dict],
) -> tuple[str, str, str]:
    recommendation = _normalize_recommendation(level, recommendation)
    ai_result = _ai_report_text(
        doc, applicant_name, level, risk_items, recommendation, amount_checks
    )
    if ai_result:
        summary, suggestion, ai_recommendation = ai_result
        return summary, suggestion, _normalize_recommendation(level, ai_recommendation)
    summary, suggestion = _fallback_report_text(doc, level, risk_items, recommendation)
    return summary, suggestion, recommendation


def generate_report(db: Session, doc: Document, auth: AuthUser | None = None, commit: bool = False) -> Report:
    existing = get_by_doc(db, doc.id)
    if existing:
        return existing

    analysis = db.execute(
        select(RiskAnalysis)
        .where(RiskAnalysis.document_id == doc.id)
        .order_by(RiskAnalysis.doc_version.desc(), RiskAnalysis.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    level = (analysis.overall_level if analysis else doc.risk_level) or "none"
    high = analysis.high_count if analysis else 0
    mid = analysis.mid_count if analysis else 0
    low = analysis.low_count if analysis else 0
    base_recommendation = (
        analysis.recommendation if analysis and analysis.recommendation else None
    )
    risk_items, evidence_rows = _risk_blocks(db, analysis)
    applicant_name = db.execute(select(User.real_name).where(User.id == doc.applicant_id)).scalar()
    amount_checks = _amount_checks(db, doc)
    summary, suggestion, recommendation = _compose_report_text(
        doc,
        applicant_name or "",
        level,
        risk_items,
        base_recommendation or "",
        amount_checks,
    )
    recommendation_label = RECOMMENDATION_LABELS[recommendation]

    content = {
        "doc_summary": {
            "doc_no": doc.doc_no,
            "title": doc.title,
            "doc_type": doc.doc_type,
            "applicant": applicant_name or "",
            "department": doc.department or "",
            "total_amount": money(doc.total_amount),
            "submit_time": fmt_dt(doc.submit_time),
        },
        "overall": {
            "level": level,
            "text": f"整体风险：{LEVEL_TEXT.get(level, '无风险')}（{high + mid + low} 项：高 {high} · 中 {mid} · 低 {low}）",
        },
        "amount_checks": amount_checks,
        "risk_items": risk_items,
        "evidences": evidence_rows,
        "vendor": _vendor_block(db, doc),
        "suggestion": suggestion,
        "reviews": _reviews(db, doc),
    }

    report = Report(
        document_id=doc.id,
        report_no=next_report_no(db, Report.report_no, now().date()),
        risk_score=analysis.risk_score if analysis else 0,
        risk_level=level,
        conclusion=recommendation_label,
        summary=summary,
        suggestion=suggestion,
        content=content,
        export_file_path=None,
        report_status="generated",
        create_by=auth.id if auth else doc.applicant_id,
        create_time=now(),
    )
    db.add(report)
    db.flush()
    log_service.record(
        db, "生成报告", doc_id=doc.id, user=auth, detail=f"生成风险审核报告 {report.report_no}"
    )
    if commit:
        db.commit()
    return report


def generate_for_doc(db: Session, auth: AuthUser, doc_id: int) -> dict:
    from app.services.document_service import get_visible_doc

    if not auth.is_finance_or_admin:
        raise_forbidden()
    doc = get_visible_doc(db, auth, doc_id)
    if doc.status in ("draft", "submitted", "analyzing"):
        raise_state_conflict()
    report = generate_report(db, doc, auth, commit=False)
    db.commit()
    from app.services.serializers import report_out

    return report_out(report)


def raise_forbidden():
    from app.core.errors import forbidden

    raise forbidden()


def raise_state_conflict():
    from app.core.errors import state_conflict

    raise state_conflict()


def page_reports(db: Session, auth: AuthUser, filters: dict, page: int, page_size: int) -> dict:
    from app.models import User
    from app.services.serializers import report_out
    from app.utils.pagination import page_out, paginate

    stmt = (
        select(Report, Document, User.real_name)
        .join(Document, Document.id == Report.document_id)
        .join(User, User.id == Document.applicant_id)
        .where(Document.delete_flag == 0)
    )
    if auth.role_code == "APPLICANT":
        stmt = stmt.where(Document.applicant_id == auth.id)
    elif auth.role_code == "DEPT_MANAGER":
        stmt = stmt.where(Document.department == auth.department)
    if filters.get("overall_level"):
        stmt = stmt.where(Report.risk_level == filters["overall_level"])
    keyword = (filters.get("keyword") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            Report.report_no.like(like)
            | Document.doc_no.like(like)
            | Document.title.like(like)
            | User.real_name.like(like)
        )
    stmt = stmt.order_by(Report.create_time.desc(), Report.id.desc())
    rows, total = paginate(db, stmt, page, page_size)
    items = []
    from app.services.serializers import money

    for report, doc, applicant_name in rows:
        items.append(
            {
                "report": report_out(report),
                "doc": {
                    "id": str(doc.id),
                    "doc_no": doc.doc_no,
                    "doc_type": doc.doc_type,
                    "title": doc.title,
                    "applicant_name": applicant_name or "",
                    "total_amount": money(doc.total_amount),
                    "status": doc.status,
                },
            }
        )
    return page_out(items, total, page, page_size)


def detail_by_doc(db: Session, auth: AuthUser, doc_id: int) -> dict:
    from app.core.errors import data_scope_denied, not_found
    from app.core.permissions import can_view_doc

    doc = db.get(Document, doc_id)
    if not doc or doc.delete_flag:
        from app.core.errors import not_found as _not_found

        raise _not_found()
    if not can_view_doc(auth, doc):
        raise data_scope_denied()
    report = get_by_doc(db, doc_id)
    if not report:
        raise not_found("报告不存在", code=40404)
    analysis = db.execute(
        select(RiskAnalysis)
        .where(RiskAnalysis.document_id == doc_id)
        .order_by(RiskAnalysis.doc_version.desc(), RiskAnalysis.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    risk_items = []
    evidences = []
    if analysis:
        rows = db.execute(
            select(RiskItem, RiskRule)
            .join(RiskRule, RiskRule.id == RiskItem.rule_id)
            .where(RiskItem.analysis_id == analysis.id)
            .order_by(RiskItem.risk_level.desc(), RiskItem.id)
        ).all()
        all_evidences = db.execute(
            select(RiskEvidence)
            .where(RiskEvidence.risk_item_id.in_([item.id for item, _ in rows]))
            .order_by(RiskEvidence.id)
        ).scalars().all() if rows else []
        evidence_by_item: dict[int, list[RiskEvidence]] = {}
        for evidence in all_evidences:
            evidence_by_item.setdefault(evidence.risk_item_id, []).append(evidence)
        for item, rule in rows:
            data = risk_item_out(item, rule, evidence_by_item.get(item.id, []))
            data["doc_id"] = str(doc_id)
            risk_items.append(data)
        from app.services.serializers import evidence_out

        evidences = [evidence_out(evidence) for evidence in all_evidences]
    applicant_name = db.execute(select(User.real_name).where(User.id == doc.applicant_id)).scalar()
    return {
        "report": report_out(report),
        "doc": document_out(doc, applicant_name),
        "risk_items": risk_items,
        "evidences": evidences,
    }


def _report_scope_stmt(auth: AuthUser, filters: dict):
    from app.models import User

    stmt = (
        select(Report, Document, User.real_name)
        .join(Document, Document.id == Report.document_id)
        .join(User, User.id == Document.applicant_id)
        .where(Document.delete_flag == 0)
    )
    if auth.role_code == "APPLICANT":
        stmt = stmt.where(Document.applicant_id == auth.id)
    elif auth.role_code == "DEPT_MANAGER":
        stmt = stmt.where(Document.department == auth.department)
    if filters.get("overall_level"):
        stmt = stmt.where(Report.risk_level == filters["overall_level"])
    keyword = (filters.get("keyword") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            Report.report_no.like(like)
            | Document.doc_no.like(like)
            | Document.title.like(like)
            | User.real_name.like(like)
        )
    return stmt.order_by(Report.create_time.desc(), Report.id.desc())


def export_report(db: Session, auth: AuthUser, report_id: int, fmt: str):
    from fastapi.responses import Response

    from app.core.errors import forbidden, not_found
    from app.utils.csvutil import csv_stream

    if not auth.is_finance_or_admin:
        raise forbidden()
    report = db.get(Report, report_id)
    if not report:
        raise not_found("报告不存在", code=40404)
    doc = db.get(Document, report.document_id)
    if not doc:
        raise not_found()
    export_format = (fmt or "pdf").lower()
    if export_format not in ("pdf", "excel"):
        from app.core.errors import bad_request

        raise bad_request("导出格式仅支持 pdf / excel")
    log_service.record(
        db, "查看风险报告", doc_id=doc.id, user=auth,
        detail=f"导出报告 {report.report_no}（{export_format}）",
    )
    db.commit()

    if export_format == "excel":
        content = report.content or {}
        rows = [
            ["报告编号", report.report_no],
            ["单据编号", doc.doc_no],
            ["单据标题", doc.title],
            ["申请人", content.get("doc_summary", {}).get("applicant", "")],
            ["整体风险", content.get("overall", {}).get("text", "")],
            ["处理建议", content.get("suggestion", "")],
            [],
            ["处理记录"],
            ["审批人", "意见", "时间"],
        ]
        rows.extend(
            [row.get("name", ""), row.get("content", ""), row.get("created_at", "")]
            for row in content.get("reviews", [])
        )
        return csv_stream(rows, ["项目", "内容"], f"{report.report_no}.csv")

    html = _report_html(report, doc)
    return Response(
        content=html.encode("utf-8"),
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{doc.doc_no}-{report.report_no}.html"
        },
    )


def _report_html(report: Report, doc: Document) -> str:
    content = report.content or {}
    overall = content.get("overall", {})
    checks = content.get("amount_checks", [])
    check_rows = "".join(
        f"<tr><td>{row.get('name', '')}</td><td>{row.get('doc_amount', '')}</td>"
        f"<td>{row.get('parsed_amount', '')}</td><td>{row.get('diff', '')}</td>"
        f"<td>{row.get('conclusion', '')}</td></tr>"
        for row in checks
    )
    reviews = "".join(
        f"<li>{row.get('name', '')}（{row.get('role', '')}）：{row.get('content', '')}"
        f" <small>{row.get('created_at', '')}</small></li>"
        for row in content.get("reviews", [])
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{report.report_no}</title>
<style>body{{font-family:sans-serif;margin:40px;color:#222}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccc;padding:6px;text-align:left}}</style>
</head><body>
<h1>风险审核报告</h1>
<p>报告编号：{report.report_no}　单据：{doc.doc_no} {doc.title}</p>
<p><strong>{overall.get('text', '')}</strong></p>
<table><thead><tr><th>费用类型</th><th>单据金额</th><th>解析金额</th><th>差额</th><th>结论</th></tr></thead>
<tbody>{check_rows}</tbody></table>
<h3>处理建议</h3><p>{content.get('suggestion', '')}</p>
<h3>审批意见</h3><ul>{reviews}</ul>
</body></html>"""


def export_summary(db: Session, auth: AuthUser, filters: dict):
    from app.core.errors import forbidden
    from app.models import User
    from app.utils.csvutil import csv_stream

    if not auth.is_finance_or_admin:
        raise forbidden()
    rows = db.execute(_report_scope_stmt(auth, filters)).all()
    data = [
        [
            report.report_no,
            doc.doc_no,
            doc.title,
            applicant_name or "",
            report.risk_level,
            report.conclusion,
            fmt_dt(report.create_time),
        ]
        for report, doc, applicant_name in rows
    ]
    return csv_stream(
        data,
        ["报告编号", "单据编号", "单据标题", "申请人", "风险等级", "处理建议", "生成时间"],
        "报告汇总.csv",
    )
