"""R-11 主体名称语义一致性（AI 增强）。

比对合同甲方/乙方、发票购买方/销售方、付款单据付款方/收款方等公司名称。
同一角色组内允许简称、全称、地区前缀与“有限公司/科技/集团”等后缀差异；
例如“北京云启科技”与“云启公司”判定为一致。
"""

from engine.base import EngineContext, EvidenceDraft, RuleFinding
from engine.registry import register

from app.services.risk_engine import (
    BUYER_LABELS,
    COUNTERPARTY_LABELS,
    evaluate_subject_consistency,
)


def _collect(ctx: EngineContext) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {"购买方": [], "交易对方": []}
    for att in ctx.attachments:
        for row in ctx.fields_of(att.id):
            label = str(row.get("label") or "").strip()
            value = str(row.get("value") or "").strip()
            if not value or value in ("未识别", "—", "-", "无"):
                continue
            if label in BUYER_LABELS:
                groups["购买方"].append(
                    {"label": label, "value": value, "source": att.file_name}
                )
            elif label in COUNTERPARTY_LABELS:
                groups["交易对方"].append(
                    {"label": label, "value": value, "source": att.file_name}
                )
    return {group: rows for group, rows in groups.items() if rows}


@register("R-11")
def check_subject_consistency(ctx: EngineContext, rule) -> list[RuleFinding]:
    groups = _collect(ctx)
    if not any(len(rows) >= 2 for rows in groups.values()):
        return []

    context = " ".join(
        filter(
            None,
            [
                ctx.doc.doc_type,
                ctx.doc.title,
                ctx.doc.project,
                ctx.doc.description,
                ctx.parsed_text(),
            ],
        )
    )
    judgment = evaluate_subject_consistency(groups, context)
    if judgment.get("consistent"):
        return []

    evidences: list[EvidenceDraft] = []
    for issue in judgment.get("issues", [])[:5]:
        evidences.append(
            EvidenceDraft(
                evidence_type="subject_consistency",
                snippet=(
                    f"{issue['group']}：“{issue['first']}” vs “{issue['second']}”"
                ),
                source="合同/发票/付款单据",
                page=1,
                confidence=float(judgment.get("confidence") or 88.0),
            )
        )
    if not evidences:
        for group, rows in groups.items():
            for row in rows[:3]:
                evidences.append(
                    EvidenceDraft(
                        evidence_type="subject_consistency",
                        snippet=f"{group} {row['label']}：{row['value']}",
                        source=row["source"],
                        page=1,
                        confidence=float(judgment.get("confidence") or 88.0),
                    )
                )

    reason = str(judgment.get("reason") or "公司名称疑似指向不同主体。").strip()
    engine = "AI 语义比对" if judgment.get("source") == "ai" else "名称归一化比对"
    return [
        RuleFinding(
            rule_code="R-11",
            risk_level="high",
            risk_desc=f"合同主体、发票抬头与付款对象的公司名称不一致（{engine}）：{reason}",
            score=25,
            risk_type="主体名称不一致",
            evidences=evidences,
        )
    ]
