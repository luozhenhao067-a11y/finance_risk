"""单据主表、明细、附件、解析结果、快照。"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.rbac import Base


class Document(Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    doc_type: Mapped[str] = mapped_column(String(30), nullable=False)
    doc_type_name: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    project: Mapped[str | None] = mapped_column(String(100))
    dept_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_node: Mapped[str | None] = mapped_column(String(50))
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False, default="none")
    risk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delete_flag: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    applicant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    department: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    submit_time: Mapped[datetime | None] = mapped_column(DateTime)
    finish_time: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DocumentItem(Base):
    __tablename__ = "document_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("document.id", ondelete="CASCADE"), nullable=False)
    item_no: Mapped[int] = mapped_column(Integer, nullable=False)
    expense_type: Mapped[str] = mapped_column(String(30), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    invoice_no: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Attachment(Base):
    __tablename__ = "attachment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("document.id", ondelete="CASCADE"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    parse_status: Mapped[str] = mapped_column(String(20), nullable=False, default="parsing")
    upload_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    upload_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AttachmentParseResult(Base):
    __tablename__ = "attachment_parse_result"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    attachment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("attachment.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    parse_status: Mapped[str] = mapped_column(String(20), nullable=False)
    parse_type: Mapped[str] = mapped_column(String(20), nullable=False)
    result_json: Mapped[Any | None] = mapped_column(JSON)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    error_msg: Mapped[str | None] = mapped_column(String(500))
    parse_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DocumentSnapshot(Base):
    __tablename__ = "document_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("document.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[Any] = mapped_column(JSON, nullable=False)
    immutable: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
