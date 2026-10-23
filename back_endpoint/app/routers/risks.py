"""风险中心接口。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import AuthUser, get_current_user
from app.core.response import ok
from app.database import get_db
from app.schemas.document import RerunIn
from app.services import risk_service

router = APIRouter(tags=["risks"])


@router.get("/risk-items")
def list_risk_items(
    level: str | None = None,
    status: str | None = None,
    doc_type: str | None = None,
    keyword: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = {
        "level": level,
        "status": status,
        "doc_type": doc_type,
        "keyword": keyword,
        "date_from": date_from,
        "date_to": date_to,
    }
    return ok(risk_service.list_items(db, auth, filters, page, page_size))


@router.get("/risk-items/summary")
def risk_summary(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(risk_service.summary(db, auth))


@router.put("/risk-items/{item_id}/handle")
def handle_risk_item(
    item_id: int,
    payload: dict,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        risk_service.handle_item(
            db, auth, item_id, str(payload.get("status") or ""), payload.get("opinion")
        ),
        "处理成功",
    )


@router.get("/documents/{doc_id}/risk-analysis")
def get_risk_analysis(
    doc_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(risk_service.get_analysis(db, auth, doc_id))


@router.post("/documents/{doc_id}/risk-analysis/rerun")
def rerun_risk_analysis(
    doc_id: int,
    payload: RerunIn | None = None,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reason = payload.reason if payload else None
    return ok(risk_service.rerun(db, auth, doc_id, reason), "重新分析完成")
