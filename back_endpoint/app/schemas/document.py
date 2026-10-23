"""单据相关请求体。"""

from decimal import Decimal

from pydantic import BaseModel


class DetailIn(BaseModel):
    expense_type: str = ""
    expense_date: str = ""
    amount: Decimal | None = None
    invoice_no: str | None = None
    remark: str | None = None


class AttachmentMetaIn(BaseModel):
    file_name: str = ""
    size_label: str | None = None
    size: int | None = None
    mime: str | None = None
    file_type: str | None = None


class DocumentCreateIn(BaseModel):
    doc_type: str = ""
    title: str = ""
    dept: str | None = None
    dept_id: str | None = None
    dept_name: str | None = None
    project: str | None = None
    details: list[DetailIn] = []
    attachments: list[AttachmentMetaIn] = []
    submit: bool = False
    remark: str | None = None
    description: str | None = None
    total_amount: Decimal | None = None


class SubmitIn(BaseModel):
    version: int | None = None


class RestoreIn(BaseModel):
    reason: str | None = None


class RerunIn(BaseModel):
    reason: str | None = None
