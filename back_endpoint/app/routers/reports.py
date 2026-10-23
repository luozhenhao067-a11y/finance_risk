"""报告中心接口。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import AuthUser, get_current_user
from app.core.response import ok
from app.database import get_db
from app.services import report_service

router = APIRouter(tags=["reports"])


@router.get("/reports")
def list_reports(
    keyword: str | None = None,
    overall_level: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = {"keyword": keyword, "overall_level": overall_level}
    return ok(report_service.page_reports(db, auth, filters, page, page_size))


@router.get("/reports/export-summary")
def export_summary(
    keyword: str | None = None,
    overall_level: str | None = None,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return report_service.export_summary(db, auth, {"keyword": keyword, "overall_level": overall_level})


@router.get("/reports/by-doc/{doc_id}")
def report_by_doc(
    doc_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(report_service.detail_by_doc(db, auth, doc_id))


@router.post("/documents/{doc_id}/report")
def generate_document_report(
    doc_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(report_service.generate_for_doc(db, auth, doc_id), "报告已生成")


@router.get("/reports/{report_id}/export")
def export_report(
    report_id: int,
    format: str = Query("pdf", pattern="^(pdf|excel)$"),
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return report_service.export_report(db, auth, report_id, format)
