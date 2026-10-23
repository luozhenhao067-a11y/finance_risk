"""R-07 消费异常：周末消费、连号发票、单日多票。"""

import re
from collections import defaultdict

from engine.base import EngineContext, EvidenceDraft, RuleFinding
from engine.registry import register

INVOICE_SUFFIX = re.compile(r"(\d+)$")


@register("R-07")
def check_abnormal_consumption(ctx: EngineContext, rule) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    weekend = [item for item in ctx.items if item.expense_date.weekday() >= 5]
    if weekend:
        findings.append(
            RuleFinding(
                rule_code="R-07",
                risk_level="mid",
                risk_desc=f"存在 {len(weekend)} 条周末消费记录，需核实消费真实性。",
                score=15,
                risk_type="周末消费",
                evidences=[
                    EvidenceDraft(
                        evidence_type="expense_record",
                        snippet=f"{item.expense_type} {item.expense_date} {item.amount:.2f} 元（周末）",
                        source="单据明细",
                        confidence=92.0,
                    )
                    for item in weekend
                ],
            )
        )

    groups: dict[str, list] = defaultdict(list)
    for item in ctx.items:
        if not item.invoice_no:
            continue
        match = INVOICE_SUFFIX.search(item.invoice_no)
        if not match:
            continue
        prefix = item.invoice_no[: match.start(1)]
        groups[prefix].append((int(match.group(1)), item))
    for prefix, rows in groups.items():
        rows.sort(key=lambda pair: pair[0])
        for (prev_no, prev_item), (next_no, next_item) in zip(rows, rows[1:]):
            if next_no - prev_no != 1:
                continue
            findings.append(
                RuleFinding(
                    rule_code="R-07",
                    risk_level="mid",
                    risk_desc=(
                        f"发票号 {prev_item.invoice_no} 与 {next_item.invoice_no} 连续，"
                        f"存在拆单或集中开票嫌疑。"
                    ),
                    score=15,
                    risk_type="连号发票",
                    evidences=[
                        EvidenceDraft(
                            evidence_type="invoice_record",
                            snippet=f"{item.invoice_no} {item.expense_date} {item.amount:.2f} 元",
                            source="单据明细",
                            confidence=90.0,
                        )
                        for item in (prev_item, next_item)
                    ],
                )
            )

    by_date: dict = defaultdict(list)
    for item in ctx.items:
        if item.invoice_no:
            by_date[item.expense_date].append(item)
    for expense_date, rows in by_date.items():
        if len(rows) < 3:
            continue
        findings.append(
            RuleFinding(
                rule_code="R-07",
                risk_level="mid",
                risk_desc=f"{expense_date} 单日提交 {len(rows)} 张发票，存在集中报销异常。",
                score=15,
                risk_type="单日多票",
                evidences=[
                    EvidenceDraft(
                        evidence_type="invoice_record",
                        snippet=f"{item.invoice_no} {item.amount:.2f} 元",
                        source="单据明细",
                        confidence=90.0,
                    )
                    for item in rows
                ],
            )
        )
    return findings
