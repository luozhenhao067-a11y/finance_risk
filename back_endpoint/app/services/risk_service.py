"""风险中心：分析结果查询、重跑、风险项列表/汇总/处理。"""

from sqlalchemy import case, or_, select
from sqlalchemy.orm import Session

from app.core.deps import AuthUser
from app.core.errors import bad_request, data_scope_denied, forbidden, not_found, state_conflict
from app.core.permissions import can_view_doc
from app.models import (
    Attachment,
    AttachmentParseResult,
    Document,
    RiskAnalysis,
    RiskEvidence,
    RiskItem,
    RiskRule,
    User,
)
from app.services import document_service, log_service
from app.services.serializers import (
    parse_result_out,
    risk_analysis_out,
    risk_item_out,
)
from app.utils.pagination import page_out, paginate
from app.utils.timefmt import day_after, day_start, money, now
from engine.engine import run_analysis

LEVEL_ORDER = case(
    (RiskItem.risk_level == "high", 3),
    (RiskItem.risk_level == "mid", 2),
    (RiskItem.risk_level == "low", 1),
    else_=0,
)


def _parse_results(db: Session, doc_id: int) -> list[dict]:
    attachments = db.execute(
        select(Attachment).where(Attachment.document_id == doc_id).order_by(Attachment.id)
    ).scalars().all()
    if not attachments:
        return []
    rows = db.execute(
        select(AttachmentParseResult).where(
            AttachmentParseResult.attachment_id.in_([att.id for att in attachments])
        )
    ).scalars().all()
    parse_map = {row.attachment_id: row for row in rows}
    return [parse_result_out(att, parse_map[att.id]) for att in attachments if att.id in parse_map]


def get_analysis(db: Session, auth: AuthUser, doc_id: int) -> dict:
    doc = document_service.get_visible_doc(db, auth, doc_id)
    analysis = db.execute(
        select(RiskAnalysis)
        .where(RiskAnalysis.document_id == doc.id)
        .order_by(RiskAnalysis.doc_version.desc(), RiskAnalysis.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    items = document_service._risk_items_block(db, analysis, doc.id)
    return {
        "analysis": risk_analysis_out(analysis) if analysis else None,
        "items": items,
        "parse_results": _parse_results(db, doc.id),
    }


def rerun(db: Session, auth: AuthUser, doc_id: int, reason: str | None) -> dict:
    if not auth.is_finance_or_admin:
        raise forbidden()
    doc = document_service.get_visible_doc(db, auth, doc_id)
    if doc.status not in ("pending_approval", "approved", "completed"):
        raise state_conflict()
    analysis = db.execute(
        select(RiskAnalysis)
        .where(RiskAnalysis.document_id == doc.id)
        .order_by(RiskAnalysis.doc_version.desc(), RiskAnalysis.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if analysis and analysis.status in ("pending", "analyzing"):
        raise state_conflict()
    text = (reason or "").strip() or "人工触发"
    result = run_analysis(db, doc.id, trigger_type="manual", triggered_by=auth.real_name)
    if result is None:
        raise not_found()
    log_service.record(db, "重新分析", doc_id=doc.id, user=auth, detail=f"{text}；结果 {result.overall_level}，{result.risk_count} 项风险")
    db.commit()
    return risk_analysis_out(result)


def _scoped_item_stmt(auth: AuthUser):
    stmt = (
        select(RiskItem, RiskRule, Document, RiskAnalysis, User.real_name)
        .join(RiskRule, RiskRule.id == RiskItem.rule_id)
        .join(RiskAnalysis, RiskAnalysis.id == RiskItem.analysis_id)
        .join(Document, Document.id == RiskAnalysis.document_id)
        .join(User, User.id == Document.applicant_id)
        .where(Document.delete_flag == 0, RiskAnalysis.doc_version == Document.version)
    )
    if auth.role_code == "APPLICANT":
        stmt = stmt.where(Document.applicant_id == auth.id)
    elif auth.role_code == "DEPT_MANAGER":
        stmt = stmt.where(Document.department == auth.department)
    return stmt


def list_items(db: Session, auth: AuthUser, filters: dict, page: int, page_size: int) -> dict:
    stmt = _scoped_item_stmt(auth)
    if filters.get("level"):
        stmt = stmt.where(RiskItem.risk_level == filters["level"])
    if filters.get("status"):
        stmt = stmt.where(RiskItem.status == filters["status"])
    if filters.get("doc_type"):
        stmt = stmt.where(Document.doc_type == filters["doc_type"])
    keyword = (filters.get("keyword") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                RiskRule.rule_name.like(like),
                RiskItem.risk_desc.like(like),
                Document.doc_no.like(like),
                Document.title.like(like),
                User.real_name.like(like),
            )
        )
    if filters.get("date_from"):
        try:
            stmt = stmt.where(Document.created_at >= day_start(filters["date_from"]))
        except ValueError:
            raise bad_request("开始日期格式应为 YYYY-MM-DD") from None
    if filters.get("date_to"):
        try:
            stmt = stmt.where(Document.created_at < day_after(filters["date_to"]))
        except ValueError:
            raise bad_request("结束日期格式应为 YYYY-MM-DD") from None
    status_order = case(
        (RiskItem.status == "open", 0),
        (RiskItem.status == "handled", 1),
        else_=2,
    )
    stmt = stmt.order_by(status_order.asc(), LEVEL_ORDER.desc(), RiskItem.id.desc())
    rows, total = paginate(db, stmt, page, page_size)

    items = []
    for item, rule, doc, analysis, applicant_name in rows:
        evidences = db.execute(
            select(RiskEvidence).where(RiskEvidence.risk_item_id == item.id).order_by(RiskEvidence.id)
        ).scalars().all()
        data = risk_item_out(item, rule, list(evidences))
        data["doc_id"] = str(doc.id)
        data["doc"] = {
            "id": str(doc.id),
            "doc_no": doc.doc_no,
            "doc_type": doc.doc_type,
            "title": doc.title,
            "applicant_name": applicant_name or "",
            "total_amount": money(doc.total_amount),
            "risk_level": doc.risk_level,
            "status": doc.status,
        }
        data["doc_version"] = analysis.doc_version
        items.append({"item": data, "doc": data["doc"]})
    return page_out(items, total, page, page_size)


def summary(db: Session, auth: AuthUser) -> dict:
    stmt = _scoped_item_stmt(auth)
    rows = db.execute(stmt).all()
    total_items = len(rows)
    doc_ids = {doc.id for _, _, doc, _, _ in rows}
    by_level = {"high": 0, "mid": 0, "low": 0}
    open_by_rule: dict[str, dict] = {}
    for item, rule, _, _, _ in rows:
        key = rule.risk_level if rule.risk_level in by_level else item.risk_level
        if key in by_level:
            by_level[key] += 1
        if item.status == "open":
            entry = open_by_rule.setdefault(
                rule.rule_code, {"rule_code": rule.rule_code, "title": rule.rule_name, "open_count": 0}
            )
            entry["open_count"] += 1
    top_open = sorted(open_by_rule.values(), key=lambda row: row["open_count"], reverse=True)[:5]
    return {
        "total_items": total_items,
        "doc_count": len(doc_ids),
        "by_level": by_level,
        "top_open_rules": top_open,
    }


def _item_doc(db: Session, item_id: int):
    row = db.execute(
        select(RiskItem, RiskAnalysis, Document)
        .join(RiskAnalysis, RiskAnalysis.id == RiskItem.analysis_id)
        .join(Document, Document.id == RiskAnalysis.document_id)
        .where(RiskItem.id == item_id)
    ).first()
    if not row:
        raise not_found("风险项不存在", code=40401)
    return row


def handle_item(db: Session, auth: AuthUser, item_id: int, status: str, opinion: str | None) -> dict:
    item, analysis, doc = _item_doc(db, item_id)
    if not can_view_doc(auth, doc):
        raise data_scope_denied()
    if not (auth.is_finance_or_admin or (auth.role_code == "DEPT_MANAGER" and doc.department == auth.department)):
        raise forbidden()
    if status not in ("handled", "dismissed"):
        raise bad_request("处理状态不合法")
    text = (opinion or "").strip()
    if not text:
        raise bad_request("请填写处理意见")
    if len(text) > 500:
        raise bad_request("处理意见最多 500 字")
    if item.status != "open":
        raise state_conflict()
    if doc.status not in ("pending_approval", "approved", "completed"):
        raise state_conflict()

    item.status = status
    item.handled_by = auth.real_name
    item.handled_at = now()
    item.handle_opinion = text
    log_service.record(
        db, "风险处理", doc_id=doc.id, user=auth,
        detail=f"{'标记已处理' if status == 'handled' else '排除风险'}：{text}",
    )
    db.commit()

    rule = db.get(RiskRule, item.rule_id)
    evidences = db.execute(
        select(RiskEvidence).where(RiskEvidence.risk_item_id == item.id).order_by(RiskEvidence.id)
    ).scalars().all()
    data = risk_item_out(item, rule, list(evidences))
    data["doc_id"] = str(doc.id)
    return data
