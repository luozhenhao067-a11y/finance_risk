"""工作台聚合统计。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import AuthUser
from app.models import ApprovalTask, Document, User
from app.services import notification_service
from app.services.serializers import document_out
from app.utils.timefmt import month_start

IN_APPROVAL = ("submitted", "analyzing", "pending_approval")


def _doc_scope(stmt, auth: AuthUser):
    stmt = stmt.where(Document.delete_flag == 0)
    if auth.role_code == "APPLICANT":
        return stmt.where(Document.applicant_id == auth.id)
    if auth.role_code == "DEPT_MANAGER":
        return stmt.where(Document.department == auth.department)
    return stmt


def _count(db: Session, stmt) -> int:
    return int(db.execute(stmt).scalar() or 0)


def stats(db: Session, auth: AuthUser) -> dict:
    pending_approval = _count(
        db,
        select(func.count(ApprovalTask.id))
        .join(Document, Document.id == ApprovalTask.document_id)
        .where(
            ApprovalTask.approver_id == auth.id,
            ApprovalTask.task_status == "pending",
            Document.status == "pending_approval",
            Document.delete_flag == 0,
        ),
    )
    high_risk = _count(
        db,
        _doc_scope(select(func.count(Document.id)), auth).where(Document.risk_level == "high"),
    )
    in_approval = _count(
        db,
        _doc_scope(select(func.count(Document.id)), auth).where(Document.status.in_(IN_APPROVAL)),
    )
    completed_month = _count(
        db,
        _doc_scope(select(func.count(Document.id)), auth).where(
            Document.status == "completed",
            Document.finish_time >= month_start(),
        ),
    )

    distribution = {"high": 0, "mid": 0, "low": 0}
    rows = db.execute(
        _doc_scope(select(Document.risk_level, func.count(Document.id)), auth)
        .where(Document.risk_level.in_(distribution.keys()))
        .group_by(Document.risk_level)
    ).all()
    for level, count in rows:
        distribution[level] = int(count)

    todo_rows = db.execute(
        select(ApprovalTask, Document)
        .join(Document, Document.id == ApprovalTask.document_id)
        .where(
            ApprovalTask.approver_id == auth.id,
            ApprovalTask.task_status == "pending",
            Document.status == "pending_approval",
            Document.delete_flag == 0,
        )
        .order_by(Document.submit_time.asc())
        .limit(5)
    ).all()
    todos = [
        {
            "id": str(task.id),
            "doc_id": str(doc.id),
            "level": doc.risk_level or "none",
            "text": f"{doc.doc_no} {doc.title}待审批",
        }
        for task, doc in todo_rows
    ]

    recent_rows = db.execute(
        _doc_scope(select(Document, User.real_name), auth)
        .join(User, User.id == Document.applicant_id)
        .order_by(Document.created_at.desc())
        .limit(6)
    ).all()
    recent_documents = [document_out(doc, name) for doc, name in recent_rows]

    return {
        "kpis": {
            "pending_approval": pending_approval,
            "high_risk": high_risk,
            "in_approval": in_approval,
            "completed_month": completed_month,
        },
        "risk_distribution": distribution,
        "todos": todos,
        "notifications": notification_service.latest(db, auth, 6),
        "recent_documents": recent_documents,
    }
