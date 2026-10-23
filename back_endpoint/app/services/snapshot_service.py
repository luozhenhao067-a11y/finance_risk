"""提交时点不可变快照。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.models import Attachment, Document, DocumentItem, DocumentSnapshot, User
from app.services.serializers import attachment_out, decimal_str, document_out, item_out
from app.utils.timefmt import fmt_dt, now


def _payload(db: Session, doc: Document) -> dict:
    applicant_name = db.execute(select(User.real_name).where(User.id == doc.applicant_id)).scalar()
    items = db.execute(
        select(DocumentItem).where(DocumentItem.document_id == doc.id).order_by(DocumentItem.item_no)
    ).scalars().all()
    attachments = db.execute(
        select(Attachment).where(Attachment.document_id == doc.id).order_by(Attachment.id)
    ).scalars().all()
    doc_dict = document_out(doc, applicant_name)
    doc_dict["total_amount"] = decimal_str(doc.total_amount)
    return {
        "document": doc_dict,
        "details": [item_out(item) for item in items],
        "attachments": [attachment_out(att) for att in attachments],
    }


def ensure_version(db: Session, doc: Document) -> None:
    """该版本快照已存在（如驳回恢复后再次提交）则升版，避免 uk 冲突。"""
    exists = db.execute(
        select(DocumentSnapshot.id).where(
            DocumentSnapshot.document_id == doc.id, DocumentSnapshot.version == doc.version
        )
    ).first()
    if exists:
        doc.version += 1


def create_snapshot(db: Session, doc: Document) -> DocumentSnapshot:
    snapshot = DocumentSnapshot(
        document_id=doc.id,
        version=doc.version,
        payload=_payload(db, doc),
        immutable=1,
        created_at=now(),
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def list_snapshots(db: Session, doc_id: int) -> list[dict]:
    rows = db.execute(
        select(DocumentSnapshot)
        .where(DocumentSnapshot.document_id == doc_id)
        .order_by(DocumentSnapshot.version.desc())
    ).scalars().all()
    return [
        {
            "id": str(row.id),
            "doc_id": str(row.document_id),
            "version": row.version,
            "created_at": fmt_dt(row.created_at),
            "immutable": bool(row.immutable),
        }
        for row in rows
    ]


def get_snapshot(db: Session, doc_id: int, version: int) -> dict:
    row = db.execute(
        select(DocumentSnapshot).where(
            DocumentSnapshot.document_id == doc_id, DocumentSnapshot.version == version
        )
    ).scalar_one_or_none()
    if not row:
        raise not_found("快照不存在", code=40404)
    return {
        "id": str(row.id),
        "doc_id": str(row.document_id),
        "version": row.version,
        "created_at": fmt_dt(row.created_at),
        "immutable": bool(row.immutable),
        "payload": row.payload,
    }
