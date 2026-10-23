"""通知接口。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import AuthUser, get_current_user
from app.core.response import ok
from app.database import get_db
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(notification_service.list_page(db, auth, page, page_size))


@router.put("/read-all")
def read_all(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification_service.read_all(db, auth)
    return ok(None, "已全部标记为已读")
