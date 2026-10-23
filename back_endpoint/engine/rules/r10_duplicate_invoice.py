"""R-10 重复票据：同一发票号出现在其他有效单据中。"""

from sqlalchemy import select

from app.models import Document, DocumentItem
from engine.base import EngineContext, EvidenceDraft, RuleFinding
from engine.registry import register


@register("R-10")
def check_duplicate_invoice(ctx: EngineContext, rule) -> list[RuleFinding]:
    invoice_nos = sorted({item.invoice_no for item in ctx.items if item.invoice_no})
    findings: list[RuleFinding] = []
    for invoice_no in invoice_nos:
        rows = ctx.db.execute(
            select(Document.doc_no, Document.title, DocumentItem.expense_date, DocumentItem.amount)
            .join(DocumentItem, DocumentItem.document_id == Document.id)
            .where(
                DocumentItem.invoice_no == invoice_no,
                Document.id != ctx.doc.id,
                Document.delete_flag == 0,
                Document.status != "draft",
            )
            .order_by(Document.id)
        ).all()
        if not rows:
            continue
        other = rows[0]
        findings.append(
            RuleFinding(
                rule_code="R-10",
                risk_level="high",
                risk_desc=(
                    f"发票号 {invoice_no} 已在单据 {other.doc_no}（{other.title}）中使用，"
                    f"疑似重复报销。"
                ),
                score=30,
                risk_type="重复发票",
                evidences=[
                    EvidenceDraft(
                        evidence_type="duplicate_invoice",
                        snippet=(
                            f"本单发票 {invoice_no}；历史单据 {row.doc_no} "
                            f"{row.expense_date} {row.amount:.2f} 元"
                        ),
                        source=row.doc_no,
                        confidence=97.0,
                    )
                    for row in rows[:5]
                ],
            )
        )
    return findings
