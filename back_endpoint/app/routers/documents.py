"""单据主链路接口（附件/风险/报告子路径见各自 router）。"""

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import AuthUser, get_current_user
from app.core.response import ok
from app.database import get_db
from app.schemas.common import ReasonIn
from app.schemas.document import DocumentCreateIn, SubmitIn
from app.services import approval_service, document_service, workflow

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
def list_documents(
    keyword: str | None = None,
    doc_type: str | None = None,
    status: str | None = None,
    risk_level: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = {
        "keyword": keyword,
        "doc_type": doc_type,
        "status": status,
        "risk_level": risk_level,
        "date_from": date_from,
        "date_to": date_to,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }
    return ok(document_service.get_page(db, auth, filters, page, page_size))


@router.post("")
def create_document(
    payload: DocumentCreateIn,
    background: BackgroundTasks,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = document_service.create_document(db, auth, payload)
    if payload.submit:
        background.add_task(workflow.submit_chain, int(data["id"]))
    return ok(data, "创建成功")


@router.get("/{doc_id}")
def document_detail(
    doc_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(document_service.get_detail(db, auth, doc_id))


@router.post("/{doc_id}/submit")
def submit_document(
    doc_id: int,
    background: BackgroundTasks,
    payload: SubmitIn | None = None,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    version = payload.version if payload else None
    data = document_service.submit_document(db, auth, doc_id, version)
    background.add_task(workflow.submit_chain, doc_id)
    return ok(data, "提交成功")


@router.post("/{doc_id}/resubmit")
def resubmit_document(
    doc_id: int,
    background: BackgroundTasks,
    payload: SubmitIn | None = None,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    version = payload.version if payload else None
    data = document_service.resubmit_document(db, auth, doc_id, version)
    background.add_task(workflow.submit_chain, doc_id)
    return ok(data, "重新提交成功")


@router.post("/{doc_id}/withdraw")
def withdraw_document(
    doc_id: int,
    payload: ReasonIn | None = None,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reason = payload.reason if payload else None
    return ok(document_service.withdraw_document(db, auth, doc_id, reason), "已撤回")


@router.post("/{doc_id}/complete")
def complete_document(
    doc_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(document_service.complete_document(db, auth, doc_id), "已完成")


@router.post("/{doc_id}/restore")
def restore_document(
    doc_id: int,
    payload: ReasonIn,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(document_service.restore_document(db, auth, doc_id, payload.reason), "已恢复")


@router.post("/{doc_id}/approve")
def approve_document(
    doc_id: int,
    payload: dict,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = approval_service.approve(
        db,
        auth,
        doc_id,
        action=str(payload.get("action") or ""),
        opinion=payload.get("opinion"),
        version=payload.get("version"),
    )
    return ok(data, "审批完成")


@router.get("/{doc_id}/approval-flow")
def approval_flow(
    doc_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = document_service.get_visible_doc(db, auth, doc_id)
    return ok(approval_service.flow_chain(db, doc))


@router.get("/{doc_id}/logs")
def document_logs(
    doc_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(document_service.get_logs_page(db, auth, doc_id, page, page_size))


@router.get("/{doc_id}/snapshots")
def snapshot_list(
    doc_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(document_service.list_snapshots(db, auth, doc_id))


@router.get("/{doc_id}/snapshots/{version}")
def snapshot_detail(
    doc_id: int,
    version: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(document_service.get_snapshot(db, auth, doc_id, version))
