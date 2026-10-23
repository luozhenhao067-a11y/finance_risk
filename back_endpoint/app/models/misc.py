"""审计日志、通知、报告、费用标准、供应商、字典。"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.rbac import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("document.id", ondelete="SET NULL")
    )
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str | None] = mapped_column(String(50))
    trace_id: Mapped[str | None] = mapped_column(String(40))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    detail: Mapped[str | None] = mapped_column(String(500))
    ip: Mapped[str | None] = mapped_column(String(45))
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("document.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str | None] = mapped_column(String(500))
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="approval")
    is_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Report(Base):
    __tablename__ = "report"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("document.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    report_no: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False, default="low")
    conclusion: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    suggestion: Mapped[str | None] = mapped_column(Text)
    content: Mapped[Any | None] = mapped_column(JSON)
    export_file_path: Mapped[str | None] = mapped_column(String(500))
    report_status: Mapped[str] = mapped_column(String(20), nullable=False, default="generated")
    create_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ExpenseStandard(Base):
    __tablename__ = "expense_standard"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    city: Mapped[str] = mapped_column(String(30), nullable=False)
    position_level: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="晚")
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)


class Vendor(Base):
    __tablename__ = "vendor"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    score: Mapped[int | None] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False, default="low")
    blacklist: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    established_date: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)


class DictTable(Base):
    __tablename__ = "dict"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dict_type: Mapped[str] = mapped_column(String(30), nullable=False)
    dict_label: Mapped[str] = mapped_column(String(50), nullable=False)
    dict_value: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
