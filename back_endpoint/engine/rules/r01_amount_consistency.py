"""R-01 金额一致性：发票解析金额合计 vs 单据金额。"""

from decimal import Decimal, InvalidOperation

from engine.base import EngineContext, EvidenceDraft, RuleFinding
from engine.registry import register

TOLERANCE = Decimal("0.01")


def _money(value: str) -> Decimal | None:
    cleaned = value.replace("¥", "").replace("￥", "").replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


@register("R-01")
def check_amount_consistency(ctx: EngineContext, rule) -> list[RuleFinding]:
    parsed_total = Decimal("0.00")
    evidences: list[EvidenceDraft] = []
    for att in ctx.attachments:
        raw = ctx.field_value(att.id, "金额合计")
        if not raw:
            continue
        amount = _money(raw)
        if amount is None:
            continue
        parsed_total += amount
        result = ctx.parse_results.get(att.id)
        evidences.append(
            EvidenceDraft(
                evidence_type="invoice_parse",
                snippet=f"{att.file_name} 识别金额合计 {raw}",
                source=att.file_name,
                attachment_id=att.id,
                confidence=float(result.confidence or 90) if result and result.confidence is not None else 90.0,
            )
        )

    if not evidences:
        return []

    doc_total = Decimal(str(ctx.doc.total_amount or 0))
    diff = parsed_total - doc_total
    if abs(diff) <= TOLERANCE:
        return []

    return [
        RuleFinding(
            rule_code="R-01",
            risk_level="high",
            risk_desc=(
                f"发票解析金额合计 {parsed_total:.2f} 元与单据申报金额 {doc_total:.2f} 元不一致，"
                f"差额 {diff:+.2f} 元，超过容差 0.01 元。"
            ),
            score=30,
            risk_type="金额不一致",
            evidences=evidences,
        )
    ]
