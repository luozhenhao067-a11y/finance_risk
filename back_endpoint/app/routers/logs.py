"""审计日志接口（财务/管理员）。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import AuthUser, require_finance_or_admin
from app.core.response import ok
from app.database import get_db
from app.services import log_service

router = APIRouter(prefix="/logs", tags=["logs"])


def _filters(
    keyword: str | None,
    action: str | None,
    operator: str | None,
    date_from: str | None,
    date_to: str | None,
    sort_by: str | None,
    sort_order: str | None,
) -> dict:
    return {
        "keyword": keyword,
        "action": action,
        "operator": operator,
        "date_from": date_from,
        "date_to": date_to,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }


@router.get("")
def list_logs(
    keyword: str | None = None,
    action: str | None = None,
    operator: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    auth: AuthUser = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    filters = _filters(keyword, action, operator, date_from, date_to, sort_by, sort_order)
    return ok(log_service.page(db, auth, filters, page, page_size))


@router.get("/export")
def export_logs(
    keyword: str | None = None,
    action: str | None = None,
    operator: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    auth: AuthUser = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    filters = _filters(keyword, action, operator, date_from, date_to, sort_by, sort_order)
    return log_service.export(db, filters)
