"""站内通知。"""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.deps import AuthUser
from app.models import Notification
from app.utils.pagination import paginate_scalars, page_out
from app.utils.timefmt import now, reltime


def notify(
    db: Session,
    user_id: int | None,
    doc_id: int | None,
    title: str,
    content: str | None = None,
    type_: str = "approval",
) -> None:
    if not user_id:
        return
    db.add(
        Notification(
            user_id=user_id,
            document_id=doc_id,
            title=title[:100],
            content=(content or "")[:500] or None,
            type=type_,
            is_read=0,
            create_time=now(),
        )
    )


def notification_out(row: Notification) -> dict:
    return {
        "id": str(row.id),
        "doc_id": str(row.document_id) if row.document_id else None,
        "title": row.title,
        "content": row.content or "",
        "type": row.type,
        "time": reltime(row.create_time),
        "read": bool(row.is_read),
    }


def list_page(db: Session, auth: AuthUser, page_no: int, page_size: int) -> dict:
    stmt = (
        select(Notification)
        .where(Notification.user_id == auth.id)
        .order_by(Notification.is_read.asc(), Notification.create_time.desc())
    )
    rows, total = paginate_scalars(db, stmt, page_no, page_size)
    return page_out([notification_out(row) for row in rows], total, page_no, page_size)


def latest(db: Session, auth: AuthUser, limit: int = 6) -> list[dict]:
    rows = db.execute(
        select(Notification)
        .where(Notification.user_id == auth.id)
        .order_by(Notification.is_read.asc(), Notification.create_time.desc())
        .limit(limit)
    ).scalars().all()
    return [notification_out(row) for row in rows]


def read_all(db: Session, auth: AuthUser) -> None:
    db.execute(update(Notification).where(Notification.user_id == auth.id).values(is_read=1))
    db.commit()
