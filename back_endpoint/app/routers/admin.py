"""系统管理接口（ADMIN）。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import AuthUser, require_admin
from app.core.response import ok
from app.database import get_db
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    auth: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return ok(admin_service.users_page(db, keyword, page, page_size))


@router.get("/depts")
def list_depts(
    auth: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return ok(admin_service.depts(db))


@router.get("/risk-rules")
def list_risk_rules(
    auth: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return ok(admin_service.risk_rules(db))


@router.put("/risk-rules/{code}")
def update_risk_rule(
    code: str,
    patch: dict,
    auth: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return ok(admin_service.update_rule(db, auth, code, patch), "规则已更新")
