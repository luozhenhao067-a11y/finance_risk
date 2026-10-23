"""审批待办/已办接口。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import AuthUser, get_current_user
from app.core.response import ok
from app.database import get_db
from app.services import approval_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/todo")
def todo(
    doc_type: str | None = None,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(approval_service.todo(db, auth, doc_type))


@router.get("/done")
def done(
    doc_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(approval_service.done(db, auth, doc_type, page, page_size))
