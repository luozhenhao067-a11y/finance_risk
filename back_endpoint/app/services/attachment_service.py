"""附件：上传、下载/预览、删除、解析结果。"""

from pathlib import Path
from urllib.parse import quote

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import AuthUser
from app.core.errors import bad_request, data_scope_denied, forbidden, not_found, state_conflict
from app.core.permissions import can_view_doc, is_owner
from app.models import Attachment, AttachmentParseResult, Document
from app.services import document_service, log_service
from app.services.serializers import attachment_out, parse_result_out
from app.utils.storage import (
    delete_file,
    ext_of,
    file_type_of,
    mime_of,
    resolve_path,
    save_upload,
)
from app.utils.timefmt import now

EDITABLE_STATUS = ("draft", "returned")


def list_attachments(db: Session, auth: AuthUser, doc_id: int) -> list[dict]:
    document_service.get_visible_doc(db, auth, doc_id)
    rows = db.execute(
        select(Attachment).where(Attachment.document_id == doc_id).order_by(Attachment.id)
    ).scalars().all()
    return [attachment_out(row) for row in rows]


def upload(db: Session, auth: AuthUser, doc_id: int, files: list[UploadFile]) -> list[dict]:
    doc = document_service.get_visible_doc(db, auth, doc_id)
    if not is_owner(auth, doc):
        raise data_scope_denied()
    if doc.status not in EDITABLE_STATUS:
        raise state_conflict()
    if not files:
        raise bad_request("请选择要上传的文件")

    created: list[Attachment] = []
    for upload_file in files:
        file_name = (upload_file.filename or "").strip()
        if not file_name:
            raise bad_request("附件文件名不能为空")
        ext = ext_of(file_name)
        if ext not in settings.allowed_extensions:
            raise bad_request("格式不支持，仅支持 PDF / PNG / JPG")
        content = upload_file.file.read()
        if len(content) > settings.max_upload_bytes:
            raise bad_request("单个附件不能超过 20MB")
        if not content:
            raise bad_request("附件内容为空")
        rel_url, _ = save_upload(doc.doc_no, doc.version, file_name, content)
        att = Attachment(
            document_id=doc.id,
            file_name=file_name,
            file_type=file_type_of(file_name),
            file_size=max(1, len(content) // 1024),
            file_url=rel_url,
            parse_status="parsing",
            upload_by=auth.id,
            upload_time=now(),
        )
        db.add(att)
        db.flush()
        log_service.record(db, "上传附件", doc_id=doc.id, user=auth, detail=f"上传附件 {file_name}")
        created.append(att)
    db.commit()
    return [attachment_out(att) for att in created]


def _get_attachment(db: Session, att_id: int) -> Attachment:
    att = db.get(Attachment, att_id)
    if not att:
        raise not_found("附件不存在", code=40402)
    return att


def _attachment_file(db: Session, auth: AuthUser, att_id: int) -> tuple[Attachment, Path]:
    att = _get_attachment(db, att_id)
    doc = db.get(Document, att.document_id)
    if not doc or not can_view_doc(auth, doc):
        raise data_scope_denied()
    path = resolve_path(att.file_url)
    if not path:
        raise not_found("附件文件不存在", code=40402)
    return att, path


def download_file(db: Session, auth: AuthUser, att_id: int) -> tuple[Path, str, str]:
    att, path = _attachment_file(db, auth, att_id)
    disposition = f"attachment; filename*=UTF-8''{quote(att.file_name)}"
    return path, mime_of(att.file_name), disposition


def preview_file(db: Session, auth: AuthUser, att_id: int) -> tuple[Path, str, str]:
    att, path = _attachment_file(db, auth, att_id)
    disposition = f"inline; filename*=UTF-8''{quote(att.file_name)}"
    return path, mime_of(att.file_name), disposition


def delete_attachment(db: Session, auth: AuthUser, att_id: int) -> None:
    att = _get_attachment(db, att_id)
    doc = db.get(Document, att.document_id)
    if not doc:
        raise not_found()
    if not is_owner(auth, doc):
        raise forbidden()
    if doc.status not in EDITABLE_STATUS:
        raise state_conflict()
    delete_file(att.file_url)
    log_service.record(db, "删除附件", doc_id=doc.id, user=auth, detail=f"删除附件 {att.file_name}")
    db.delete(att)
    db.commit()


def get_parse_result(db: Session, auth: AuthUser, att_id: int) -> dict:
    att = _get_attachment(db, att_id)
    doc = db.get(Document, att.document_id)
    if not doc or not can_view_doc(auth, doc):
        raise data_scope_denied()
    result = db.execute(
        select(AttachmentParseResult).where(AttachmentParseResult.attachment_id == att.id)
    ).scalar_one_or_none()
    if result is None:
        if att.parse_status == "parsing":
            return {
                "id": str(att.id),
                "doc_id": str(att.document_id),
                "attachment_id": str(att.id),
                "file_name": att.file_name,
                "page": 1,
                "raw_text": "",
                "fields": [],
                "confidence": 0.0,
                "parse_status": "parsing",
                "error_msg": None,
            }
        raise not_found("解析结果不存在", code=40402)
    return parse_result_out(att, result)
