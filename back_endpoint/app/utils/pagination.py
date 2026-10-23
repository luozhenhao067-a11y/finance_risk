"""分页与排序工具。"""

from fastapi import Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def page_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> tuple[int, int]:
    return page, page_size


def count_of(db: Session, stmt) -> int:
    return int(db.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar() or 0)


def paginate(db: Session, stmt, page: int, page_size: int):
    """返回 (rows, total)；rows 为 Row 元组，实体查询用 paginate_scalars。"""
    total = count_of(db, stmt)
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return rows, total


def paginate_scalars(db: Session, stmt, page: int, page_size: int):
    total = count_of(db, stmt)
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return rows, total


def page_out(rows: list, total: int, page: int, page_size: int) -> dict:
    return {"total": total, "page": page, "page_size": page_size, "list": rows}


def sort_apply(stmt, columns: dict, sort_by: str | None, sort_order: str | None, default_key: str):
    key = sort_by if sort_by in columns else default_key
    col = columns[key]
    descending = (sort_order or "desc").lower() != "asc"
    return stmt.order_by(col.desc() if descending else col.asc())
