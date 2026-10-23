"""审批流、任务、意见。"""

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.rbac import Base


class ApprovalFlow(Base):
    __tablename__ = "approval_flow"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("document.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    flow_name: Mapped[str] = mapped_column(String(100), nullable=False)
    current_node: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_nodes: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    start_time: Mapped[object] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[object | None] = mapped_column(DateTime)


class ApprovalTask(Base):
    __tablename__ = "approval_task"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    flow_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("approval_flow.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("document.id", ondelete="CASCADE"), nullable=False
    )
    node_no: Mapped[int] = mapped_column(Integer, nullable=False)
    node_name: Mapped[str] = mapped_column(String(50), nullable=False)
    approver_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    task_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    action: Mapped[str | None] = mapped_column(String(20))
    assign_time: Mapped[object] = mapped_column(DateTime, nullable=False)
    handle_time: Mapped[object | None] = mapped_column(DateTime)


class ApprovalOpinion(Base):
    __tablename__ = "approval_opinion"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int | None] = mapped_column(BigInteger)
    opinion: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    node: Mapped[str | None] = mapped_column(String(50))
    create_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    create_time: Mapped[object] = mapped_column(DateTime, nullable=False)
