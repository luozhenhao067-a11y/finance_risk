"""附件接口（含单据维度子路径）。"""

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import AuthUser, get_current_user
from app.core.response import ok
from app.database import get_db
from app.services import attachment_service, workflow

router = APIRouter(tags=["attachments"])


@router.get("/documents/{doc_id}/attachments")
def list_attachments(
    doc_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(attachment_service.list_attachments(db, auth, doc_id))


@router.post("/documents/{doc_id}/attachments")
def upload_attachments(
    doc_id: int,
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = attachment_service.upload(db, auth, doc_id, files)
    for row in data:
        background.add_task(workflow.parse_chain, int(row["id"]))
    return ok(data, "上传成功")


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    path, media_type, disposition = attachment_service.download_file(db, auth, attachment_id)
    return FileResponse(path, media_type=media_type, headers={"Content-Disposition": disposition})


@router.get("/attachments/{attachment_id}/preview")
def preview_attachment(
    attachment_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    path, media_type, disposition = attachment_service.preview_file(db, auth, attachment_id)
    return FileResponse(path, media_type=media_type, headers={"Content-Disposition": disposition})


@router.delete("/attachments/{attachment_id}")
def delete_attachment(
    attachment_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attachment_service.delete_attachment(db, auth, attachment_id)
    return ok(None, "删除成功")


@router.get("/attachments/{attachment_id}/parse-result")
def attachment_parse_result(
    attachment_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(attachment_service.get_parse_result(db, auth, attachment_id))
