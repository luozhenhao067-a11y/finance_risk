"""审计日志：唯一写入口（append-only）。"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import AuthUser
from app.core.trace import get_req_meta, get_trace_id
from app.models import AuditLog, Document, User
from app.utils.csvutil import csv_stream
from app.utils.pagination import paginate, page_out, sort_apply
from app.utils.timefmt import day_after, day_start, fmt_dt, now


def record(
    db: Session,
    action: str,
    *,
    doc_id: int | None = None,
    detail: str | None = None,
    user: AuthUser | None = None,
    role: str | None = None,
) -> AuditLog:
    meta = get_req_meta()
    log = AuditLog(
        document_id=doc_id,
        user_id=user.id if user else None,
        action=action,
        role=role or (user.role_name if user else "系统"),
        trace_id=get_trace_id() or None,
        user_agent=meta.get("user_agent") or None,
        detail=(detail or "")[:500] or None,
        ip=meta.get("ip") or None,
        create_time=now(),
    )
    db.add(log)
    return log


def log_out(log: AuditLog, operator_name: str | None = None, doc: Document | None = None) -> dict:
    data = {
        "id": str(log.id),
        "doc_id": str(log.document_id) if log.document_id else None,
        "action": log.action,
        "operator": operator_name or "系统",
        "role": log.role or "系统",
        "detail": log.detail or "",
        "created_at": fmt_dt(log.create_time),
    }
    if doc is not None:
        data["doc"] = {"id": str(doc.id), "doc_no": doc.doc_no, "title": doc.title}
    return data


def page(db: Session, auth: AuthUser, filters: dict, page_no: int, page_size: int) -> dict:
    stmt = (
        select(AuditLog, User.real_name, Document)
        .outerjoin(User, User.id == AuditLog.user_id)
        .outerjoin(Document, Document.id == AuditLog.document_id)
    )
    keyword = (filters.get("keyword") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                AuditLog.action.like(like),
                AuditLog.detail.like(like),
                AuditLog.role.like(like),
                User.real_name.like(like),
                Document.doc_no.like(like),
                Document.title.like(like),
            )
        )
    if filters.get("action"):
        stmt = stmt.where(AuditLog.action == filters["action"])
    if filters.get("operator"):
        stmt = stmt.where(User.real_name == filters["operator"])
    if filters.get("date_from"):
        stmt = stmt.where(AuditLog.create_time >= day_start(filters["date_from"]))
    if filters.get("date_to"):
        stmt = stmt.where(AuditLog.create_time < day_after(filters["date_to"]))
    stmt = sort_apply(stmt, {"create_time": AuditLog.create_time}, filters.get("sort_by"), filters.get("sort_order"), "create_time")
    rows, total = paginate(db, stmt, page_no, page_size)
    items = [log_out(log, name, doc) for log, name, doc in rows]
    return page_out(items, total, page_no, page_size)


def page_for_doc(db: Session, doc_id: int, page_no: int, page_size: int) -> dict:
    stmt = (
        select(AuditLog, User.real_name)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(AuditLog.document_id == doc_id)
        .order_by(AuditLog.create_time.desc(), AuditLog.id.desc())
    )
    rows, total = paginate(db, stmt, page_no, page_size)
    items = [log_out(log, name) for log, name in rows]
    return page_out(items, total, page_no, page_size)


def recent_for_doc(db: Session, doc_id: int, limit: int = 50) -> list[dict]:
    rows = db.execute(
        select(AuditLog, User.real_name)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(AuditLog.document_id == doc_id)
        .order_by(AuditLog.create_time.desc())
        .limit(limit)
    ).all()
    return [log_out(log, name) for log, name in rows]


def export(db: Session, filters: dict):
    stmt = (
        select(AuditLog, User.real_name, Document)
        .outerjoin(User, User.id == AuditLog.user_id)
        .outerjoin(Document, Document.id == AuditLog.document_id)
    )
    keyword = (filters.get("keyword") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(AuditLog.action.like(like), AuditLog.detail.like(like), User.real_name.like(like)))
    if filters.get("action"):
        stmt = stmt.where(AuditLog.action == filters["action"])
    if filters.get("operator"):
        stmt = stmt.where(User.real_name == filters["operator"])
    stmt = stmt.order_by(AuditLog.create_time.desc()).limit(5000)
    rows = db.execute(stmt).all()
    data = [
        [
            fmt_dt(log.create_time),
            name or "系统",
            log.role or "系统",
            log.action,
            doc.doc_no if doc else "",
            doc.title if doc else "",
            log.detail or "",
            log.trace_id or "",
            log.ip or "",
        ]
        for log, name, doc in rows
    ]
    headers = ["时间", "操作人", "角色", "操作", "单据编号", "单据标题", "详情", "trace_id", "IP"]
    return csv_stream(data, headers, "审计日志.csv")
