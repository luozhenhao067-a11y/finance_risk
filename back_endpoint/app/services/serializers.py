"""DB 行 → 契约 API 形状的映射。"""

import json
from datetime import date, datetime
from decimal import Decimal

from app.models import (
    ApprovalFlow,
    ApprovalOpinion,
    ApprovalTask,
    Attachment,
    AttachmentParseResult,
    Document,
    DocumentItem,
    Report,
    RiskAnalysis,
    RiskEvidence,
    RiskItem,
    RiskRule,
    User,
)
from app.utils.ids import dept_pseudo_id
from app.utils.storage import file_type_of, mime_of, size_label
from app.utils.timefmt import fmt_d, fmt_dt, money

RULE_SUGGESTIONS = {
    "R-01": "核对明细金额并更正，或补充差额说明",
    "R-05": "核实是否符合差旅标准，超标部分需说明",
    "R-07": "核实消费真实性，提供必要说明",
    "R-09": "补充所需附件并重新上传",
    "R-10": "核实发票是否重复使用，提供说明",
    "R-11": "核对合同主体、发票抬头与收款方，补充名称一致性说明",
    "R-12": "核实消费金额合理性，补充费用明细或审批说明",
    "R-EXT": "按扩展规则要求补充说明",
}

LEVEL_TO_API = {"medium": "mid", "mid": "mid", "high": "high", "low": "low", "none": "none"}
LEVEL_RANK = {"none": 0, "low": 1, "mid": 2, "high": 3}


def _to_float(value) -> float | None:
    return None if value is None else float(value)


def confidence_percent(value) -> float:
    """DB 置信度可能是 0.97（分制）或 96.00（百分制）。"""
    if value is None:
        return 0.0
    number = float(value)
    if number <= 1:
        number *= 100
    return round(number, 2)


def admin_user_out(user: User, role_name: str | None = None) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "name": user.real_name,
        "role": role_name or "",
        "dept": user.department or "",
        "position": user.position or "",
        "phone": user.phone or "",
        "email": user.email or "",
        "status": user.status,
    }


def document_out(doc: Document, applicant_name: str | None = None) -> dict:
    return {
        "id": str(doc.id),
        "doc_no": doc.doc_no,
        "doc_type": doc.doc_type,
        "title": doc.title,
        "applicant_id": str(doc.applicant_id),
        "applicant_name": applicant_name or "",
        "dept_id": dept_pseudo_id(doc.department),
        "dept_name": doc.department or "",
        "project": doc.project or "",
        "total_amount": money(doc.total_amount),
        "status": doc.status,
        "version": doc.version,
        "current_node": doc.current_node,
        "submit_time": fmt_dt(doc.submit_time),
        "create_time": fmt_dt(doc.created_at),
        "risk_level": doc.risk_level,
        "risk_count": doc.risk_count,
        "queue_time": "",
        "remark": doc.description or "",
    }


def item_out(item: DocumentItem) -> dict:
    return {
        "id": str(item.id),
        "doc_id": str(item.document_id),
        "expense_type": item.expense_type,
        "expense_date": fmt_d(item.expense_date),
        "amount": money(item.amount),
        "invoice_no": item.invoice_no or "",
        "remark": item.description or "",
    }


def attachment_out(att: Attachment) -> dict:
    return {
        "id": str(att.id),
        "doc_id": str(att.document_id),
        "file_name": att.file_name,
        "size": int(att.file_size or 0) * 1024,
        "size_label": size_label(int(att.file_size or 0)),
        "mime": mime_of(att.file_name),
        "file_type": att.file_type or file_type_of(att.file_name),
        "storage_path": att.file_url or "",
        "path": att.file_url or "",
        "uploaded_at": fmt_dt(att.upload_time),
        "parse_status": att.parse_status,
    }


def parse_fields(result_json) -> list[dict]:
    """兼容两种存储格式：契约 fields 数组，或发票要素 dict。

    AI 解析结果会额外携带 page / position（契约中 position 为可选字段）。
    """
    if isinstance(result_json, list):
        fields = []
        for row in result_json:
            if not isinstance(row, dict):
                continue
            field = {
                "label": str(row.get("label", "")),
                "value": str(row.get("value", "")),
                "confidence": float(row.get("confidence", 0) or 0),
            }
            if row.get("position"):
                field["position"] = str(row["position"])
            fields.append(field)
        return fields
    if isinstance(result_json, dict):
        label_map = {
            "invoice_no": "发票号码",
            "invoice_code": "发票代码",
            "invoice_date": "开票日期",
            "amount": "金额合计",
            "seller": "销售方",
            "buyer": "购买方",
            "check_status": "校验状态",
        }
        return [
            {"label": label_map.get(key, key), "value": str(value), "confidence": 96}
            for key, value in result_json.items()
        ]
    return []


def _parse_page(result_json) -> int:
    if not isinstance(result_json, list):
        return 1
    pages = []
    for row in result_json:
        if not isinstance(row, dict):
            continue
        try:
            pages.append(int(row.get("page") or 1))
        except (TypeError, ValueError):
            continue
    return max(pages) if pages else 1


def parse_result_out(att: Attachment, pr: AttachmentParseResult) -> dict:
    fields = parse_fields(pr.result_json)
    return {
        "id": str(att.id),
        "doc_id": str(att.document_id),
        "attachment_id": str(att.id),
        "file_name": att.file_name,
        "page": _parse_page(pr.result_json),
        "raw_text": " ".join(f"{row['label']} {row['value']}" for row in fields),
        "fields": fields,
        "confidence": confidence_percent(pr.confidence),
        "parse_status": att.parse_status,
        "error_msg": pr.error_msg,
    }


def analysis_status_to_api(status: str) -> str:
    return "running" if status in ("pending", "analyzing") else status


def risk_analysis_out(analysis: RiskAnalysis) -> dict:
    return {
        "id": str(analysis.id),
        "doc_id": str(analysis.document_id),
        "doc_version": analysis.doc_version,
        "analysis_no": analysis.analysis_no,
        "status": analysis_status_to_api(analysis.status),
        "overall_level": analysis.overall_level or "none",
        "high_count": analysis.high_count,
        "mid_count": analysis.mid_count,
        "low_count": analysis.low_count,
        "risk_count": analysis.risk_count,
        "risk_score": analysis.risk_score,
        "recommendation": analysis.recommendation or "pass",
        "recommendation_label": analysis.recommendation_label or "建议通过",
        "summary": analysis.summary or "",
        "trigger_type": analysis.trigger_type,
        "triggered_by": analysis.triggered_by,
        "analyzed_at": fmt_dt(analysis.analyzed_at),
    }


def _evidence_payload(ev: RiskEvidence) -> dict:
    snippet = ev.evidence_content or ""
    page = 1
    confidence = 90.0
    if snippet.strip().startswith("{"):
        try:
            data = json.loads(snippet)
            snippet = str(data.get("snippet", snippet))
            page = int(data.get("page", 1) or 1)
            confidence = float(data.get("confidence", 90) or 90)
        except (ValueError, TypeError):
            pass
    return {"snippet": snippet, "page": page, "confidence": confidence}


def evidence_out(ev: RiskEvidence) -> dict:
    payload = _evidence_payload(ev)
    return {
        "id": str(ev.id),
        "risk_item_id": str(ev.risk_item_id),
        "attachment_id": str(ev.attachment_id) if ev.attachment_id else None,
        "page": payload["page"],
        "snippet": payload["snippet"],
        "confidence": payload["confidence"],
        "source": ev.source or "",
        "evidence_type": ev.evidence_type,
    }


def risk_item_out(item: RiskItem, rule: RiskRule | None, evidences: list[RiskEvidence]) -> dict:
    ev_out = [evidence_out(ev) for ev in evidences]
    first = ev_out[0] if ev_out else None
    rule_code = rule.rule_code if rule else ""
    return {
        "id": str(item.id),
        "doc_id": None,  # 由调用方补 doc_id
        "rule_code": rule_code,
        "level": LEVEL_TO_API.get(item.risk_level, item.risk_level),
        "title": rule.rule_name if rule else item.risk_type,
        "basis": item.risk_desc,
        "evidence": first["snippet"] if first else None,
        "suggestion": RULE_SUGGESTIONS.get(rule_code)
        or (rule.description if rule and rule.description else "请复核该风险项"),
        "page": first["page"] if first else 1,
        "confidence": first["confidence"] if first else 90.0,
        "status": item.status,
        "handled_by": item.handled_by,
        "handled_at": fmt_dt(item.handled_at),
        "handle_opinion": item.handle_opinion,
        "evidences": ev_out,
    }


def flow_out(flow: ApprovalFlow) -> dict:
    from app.services.state_machine import NODE_NAMES

    current = None
    if flow.status == "running" and 1 <= flow.current_node <= len(NODE_NAMES):
        current = NODE_NAMES[flow.current_node - 1]
    return {
        "id": str(flow.id),
        "doc_id": str(flow.document_id),
        "status": flow.status,
        "current_node": current,
    }


def task_out(task: ApprovalTask, assignee_name: str | None) -> dict:
    return {
        "id": str(task.id),
        "instance_id": str(task.flow_id),
        "doc_id": str(task.document_id),
        "node": task.node_name,
        "assignee": assignee_name or "",
        "status": task.task_status,
        "action": task.action,
        "finished_at": fmt_dt(task.handle_time),
    }


def opinion_out(op: ApprovalOpinion, doc_id: int | None, user_name: str | None) -> dict:
    return {
        "id": str(op.id),
        "doc_id": str(doc_id) if doc_id else None,
        "task_id": str(op.task_id) if op.task_id else None,
        "node": op.node or "",
        "user": user_name or "",
        "action": op.action,
        "opinion": op.opinion,
        "created_at": fmt_dt(op.create_time),
    }


def report_out(report: Report) -> dict:
    content = report.content or {}
    overall = content.get("overall") or content.get("overall_risk") or {}
    return {
        "id": str(report.id),
        "doc_id": str(report.document_id),
        "report_no": report.report_no,
        "generated_at": fmt_dt(report.create_time),
        "overall_level": overall.get("level") or report.risk_level,
        "overall_text": overall.get("text") or "",
        "recommendation_label": report.conclusion,
        "summary": report.summary or "",
        "amount_checks": content.get("amount_checks") or [],
        "vendor": content.get("vendor"),
        "reviews": content.get("reviews") or [],
        "risk_items": content.get("risk_items") or [],
        "evidences": content.get("evidences") or [],
        "suggestion": content.get("suggestion") or report.suggestion or "",
        "doc_summary": content.get("doc_summary") or {},
    }


def rule_out(rule: RiskRule) -> dict:
    return {
        "code": rule.rule_code,
        "name": rule.rule_name,
        "level": LEVEL_TO_API.get(rule.risk_level, rule.risk_level),
        "doc_types": "全部",
        "enabled": bool(rule.enabled),
        "params": rule.params or rule.description or "",
        "threshold": _to_float(rule.threshold),
        "description": rule.description or "",
    }


def log_snapshot(value: date | datetime | None):
    return fmt_d(value) if value else None


def decimal_str(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.2f}"
