"""规则、风险分析、风险项、证据。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.rbac import Base


class RiskRule(Base):
    __tablename__ = "risk_rule"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    params: Mapped[str | None] = mapped_column(String(200))
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)


class RiskAnalysis(Base):
    __tablename__ = "risk_analysis"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("document.id", ondelete="CASCADE"), nullable=False)
    doc_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    analysis_no: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False, default="low")
    overall_level: Mapped[str | None] = mapped_column(String(10))
    high_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recommendation: Mapped[str | None] = mapped_column(String(20))
    recommendation_label: Mapped[str | None] = mapped_column(String(20))
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")
    triggered_by: Mapped[str | None] = mapped_column(String(50))
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime)
    risk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    analyzer: Mapped[str | None] = mapped_column(String(50))
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime)
    summary: Mapped[str | None] = mapped_column(Text)


class RiskItem(Base):
    __tablename__ = "risk_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("risk_analysis.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("risk_rule.id"), nullable=False)
    risk_type: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    risk_desc: Mapped[str] = mapped_column(String(500), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    handled_by: Mapped[str | None] = mapped_column(String(50))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime)
    handle_opinion: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class RiskEvidence(Base):
    __tablename__ = "risk_evidence"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    risk_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("risk_item.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_content: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(100))
    attachment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("attachment.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
