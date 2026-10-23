"""编号生成与部门伪 ID。"""

import hashlib
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session


def dept_pseudo_id(name: str | None) -> str | None:
    """无部门表：用部门名生成稳定伪 ID。"""
    if not name:
        return None
    return "dept-" + hashlib.md5(name.encode("utf-8")).hexdigest()[:6]


def next_seq(db: Session, column, stem: str, sep: str, width: int) -> str:
    """生成 {stem}{sep}{seq:0{width}d}，如 FY20261021-003 / RPT-20261021-0001。

    并发安全依赖列上的唯一索引：调用方插入冲突时重试。
    """
    prefix = f"{stem}{sep}"
    values = db.execute(select(column).where(column.like(f"{prefix}%"))).scalars().all()
    max_seq = 0
    for value in values:
        suffix = value[len(prefix):] if value.startswith(prefix) else ""
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"{prefix}{max_seq + 1:0{width}d}"


def next_doc_no(db: Session, doc_no_column, day: date) -> str:
    return next_seq(db, doc_no_column, f"FY{day:%Y%m%d}", "-", 3)


def next_analysis_no(db: Session, col, day: date) -> str:
    return next_seq(db, col, f"RA{day:%Y%m%d}", "-", 3)


def next_report_no(db: Session, col, day: date) -> str:
    return next_seq(db, col, f"RPT-{day:%Y%m%d}", "-", 4)
