"""智能问答：基于单据详情、风险项和规则，解释风险判定原因。

未配置大模型或调用失败时，根据风险项与处理建议拼接确定性回答。
"""

from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import AuthUser
from app.core.errors import bad_request
from app.models import RiskEvidence, RiskItem, RiskRule
from app.services import ai_client, approval_service, document_service, log_service

LEVEL_TEXT = {"high": "高风险", "mid": "中风险", "low": "低风险", "none": "无风险"}
STATUS_TEXT = {"open": "待处理", "handled": "已处理", "dismissed": "已排除"}
ACTION_TEXT = {
    "pass": "建议通过",
    "supplement": "补充材料",
    "manual_review": "人工复核",
    "reject_suggest": "建议驳回",
}
_RULE_CODE = re.compile(r"R-\d{2}", re.IGNORECASE)


def _unique_codes(codes) -> list[str]:
    result: list[str] = []
    for code in codes:
        text = str(code or "").strip().upper()
        if text and text not in result:
            result.append(text)
    return result


def _risk_rows(db: Session, analysis) -> list[dict]:
    if not analysis:
        return []
    rows = db.execute(
        select(RiskItem, RiskRule)
        .join(RiskRule, RiskRule.id == RiskItem.rule_id)
        .where(RiskItem.analysis_id == analysis.id)
        .order_by(RiskItem.id)
    ).all()
    if not rows:
        return []
    evidence_rows = db.execute(
        select(RiskEvidence)
        .where(RiskEvidence.risk_item_id.in_([item.id for item, _ in rows]))
        .order_by(RiskEvidence.id)
    ).scalars().all()
    evidence_by_item: dict[int, list[str]] = {}
    for evidence in evidence_rows:
        evidence_by_item.setdefault(evidence.risk_item_id, []).append(
            evidence.evidence_content or ""
        )
    return [
        {
            "rule_code": rule.rule_code,
            "title": rule.rule_name,
            "level": LEVEL_TEXT.get(item.risk_level, item.risk_level),
            "basis": item.risk_desc,
            "status": STATUS_TEXT.get(item.status, item.status),
            "handle_opinion": item.handle_opinion or "",
            "evidences": evidence_by_item.get(item.id, [])[:2],
        }
        for item, rule in rows
    ]


def _fallback_answer(doc, analysis, risks: list[dict], question: str) -> str:
    asked_codes = {code.upper() for code in _RULE_CODE.findall(question or "")}
    selected = [risk for risk in risks if risk["rule_code"].upper() in asked_codes]
    if not selected:
        selected = risks

    if not analysis:
        return (
            f"单据 {doc.doc_no}《{doc.title}》当前状态为 {doc.status}，尚未生成风险分析结果，"
            "暂时无法回答风险判定相关问题。请等待附件解析和风险分析完成后再提问。"
        )
    if not selected:
        return (
            f"单据 {doc.doc_no}《{doc.title}》风险等级为"
            f"{LEVEL_TEXT.get(analysis.overall_level or 'none', '无风险')}，"
            "当前未发现明显风险，建议按常规流程审批。"
        )

    lines = [
        f"单据 {doc.doc_no}《{doc.title}》整体风险为"
        f"{LEVEL_TEXT.get(analysis.overall_level or 'none', '无风险')}，"
        f"共触发 {len(risks)} 项风险。相关判定如下："
    ]
    for risk in selected[:5]:
        lines.append(
            f"· {risk['rule_code']} {risk['title']}（{risk['level']}，状态：{risk['status']}）："
            f"{risk['basis']}"
        )
    label = ACTION_TEXT.get(analysis.recommendation or "", analysis.recommendation_label or "")
    if label:
        lines.append(f"综合处理建议：{label}。")
    return "\n".join(lines)[:800]


def _ai_answer(doc, analysis, risks: list[dict], question: str) -> dict | None:
    if not ai_client.is_ai_enabled():
        return None
    context = {
        "单据": {
            "编号": doc.doc_no,
            "标题": doc.title,
            "类型": doc.doc_type,
            "状态": doc.status,
            "总金额": str(doc.total_amount),
            "申请人部门": doc.department or "",
            "项目": doc.project or "",
            "说明": doc.description or "",
        },
        "风险分析": {
            "整体等级": (analysis.overall_level if analysis else None) or "none",
            "风险数量": analysis.risk_count if analysis else 0,
            "处理建议": (analysis.recommendation if analysis else None) or "",
            "摘要": (analysis.summary if analysis else None) or "",
        },
        "风险项": risks,
    }
    prompt = (
        "你是财务单据智能风险审核系统的问答助手。请仅根据提供的单据、风险分析与风险项回答审批人的问题。\n"
        "要求：\n"
        "1. 用专业、客观的中文回答，先给结论再解释依据；\n"
        "2. 涉及风险时引用规则编号（如 R-01）；\n"
        "3. 不要编造未提供的数据；信息不足时明确说明；\n"
        "4. answer 不超过 500 字；related_risk_codes 只填写本次回答实际引用的规则编号。\n"
        f"上下文：{json.dumps(context, ensure_ascii=False)}\n"
        f"审批人问题：{question}\n"
        '返回严格 JSON：{"answer": "...", "related_risk_codes": ["R-01"]}'
    )
    payload = ai_client.chat_json(
        [
            {"role": "system", "content": "你是严谨的财务风控问答助手，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=900,
    )
    if not isinstance(payload, dict):
        return None
    answer = str(payload.get("answer") or "").strip()
    if not answer:
        return None
    valid_codes = {risk["rule_code"] for risk in risks}
    codes = payload.get("related_risk_codes")
    related: list[str] = []
    if isinstance(codes, list):
        for code in codes:
            text = str(code).strip().upper()
            if text in valid_codes and text not in related:
                related.append(text)
    return {"answer": answer[:800], "related_risk_codes": related}


def answer_question(db: Session, auth: AuthUser, doc_id: int, question: str) -> dict:
    text = (question or "").strip()
    if not text:
        raise bad_request("问题不能为空")
    if len(text) > 500:
        raise bad_request("问题最多 500 字")

    doc = document_service.get_visible_doc(db, auth, doc_id)
    analysis = approval_service.latest_analysis(db, doc)
    risks = _risk_rows(db, analysis)

    result = _ai_answer(doc, analysis, risks, text)
    if result is None:
        answer = _fallback_answer(doc, analysis, risks, text)
        asked_codes = {code.upper() for code in _RULE_CODE.findall(text)}
        related = _unique_codes(
            risk["rule_code"] for risk in risks if risk["rule_code"].upper() in asked_codes
        )
        if not related:
            high = _unique_codes(
                risk["rule_code"] for risk in risks if risk["level"] == "高风险"
            )
            related = high or _unique_codes(risk["rule_code"] for risk in risks[:5])
        result = {"answer": answer, "related_risk_codes": related}
    elif not result["related_risk_codes"]:
        high = _unique_codes(risk["rule_code"] for risk in risks if risk["level"] == "高风险")
        result["related_risk_codes"] = high or _unique_codes(
            risk["rule_code"] for risk in risks[:5]
        )

    log_service.record(
        db,
        "智能问答",
        doc_id=doc.id,
        user=auth,
        detail=f"提问：{text[:460]}",
    )
    db.commit()
    return result
