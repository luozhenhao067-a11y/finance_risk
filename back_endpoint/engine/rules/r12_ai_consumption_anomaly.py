"""R-12 消费异常智能检测（AI 增强）。

结合单据金额、报销类型、同类型历史均值、当前城市与费用类型判断是否异常。
未配置大模型时，使用“超过历史均值 1.5 倍”的统计阈值兜底。
"""

from decimal import Decimal

from engine.base import EngineContext, EvidenceDraft, RuleFinding
from engine.registry import register

from app.services.risk_engine import (
    detect_city,
    evaluate_consumption_anomaly,
    historical_amount_stats,
)

LEVEL_SCORE = {"high": 30, "mid": 15, "low": 5, "none": 0}


def _doc_text(ctx: EngineContext) -> str:
    return " ".join(
        filter(
            None,
            [
                ctx.doc.title,
                ctx.doc.project,
                ctx.doc.description,
                *(item.description for item in ctx.items),
                ctx.parsed_text(),
            ],
        )
    )


@register("R-12")
def check_consumption_anomaly(ctx: EngineContext, rule) -> list[RuleFinding]:
    stats = historical_amount_stats(ctx.db, ctx.doc)
    if stats["avg"] is None or stats["count"] < 3:
        return []

    city = detect_city(_doc_text(ctx))
    expense_types = sorted({item.expense_type for item in ctx.items if item.expense_type})
    threshold = float(rule.threshold) if rule.threshold is not None else 1.5
    judgment = evaluate_consumption_anomaly(
        ctx.doc,
        stats,
        city=city,
        expense_types=expense_types,
        threshold=threshold,
    )
    if not judgment.get("abnormal"):
        return []

    level = str(judgment.get("level") or "mid").lower()
    if level not in ("high", "mid", "low"):
        level = "mid"
    engine = "AI 综合判断" if judgment.get("source") == "ai" else "历史均值阈值"
    amount = Decimal(str(ctx.doc.total_amount or 0))
    reason = str(judgment.get("reason") or "").strip()

    return [
        RuleFinding(
            rule_code="R-12",
            risk_level=level,
            risk_desc=(
                f"消费金额异常（{engine}）：本单 {amount:.2f} 元，"
                f"同类型历史均值 {stats['avg']:.2f} 元（样本 {stats['count']} 单，城市 {city}）。"
                f"{reason}"
            )[:480],
            score=LEVEL_SCORE[level] or 15,
            risk_type="消费金额异常",
            evidences=[
                EvidenceDraft(
                    evidence_type="consumption_anomaly",
                    snippet=(
                        f"本单金额 {amount:.2f} 元；历史均值 {stats['avg']:.2f} 元；"
                        f"样本 {stats['count']} 单；城市 {city}；倍数 {judgment.get('ratio')}"
                    ),
                    source="历史消费数据",
                    page=1,
                    confidence=float(judgment.get("confidence") or 85.0),
                )
            ],
        )
    ]
