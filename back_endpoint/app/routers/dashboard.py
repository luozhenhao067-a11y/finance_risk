"""工作台接口。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import AuthUser, get_current_user
from app.core.response import ok
from app.database import get_db
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
def dashboard_stats(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(dashboard_service.stats(db, auth))
