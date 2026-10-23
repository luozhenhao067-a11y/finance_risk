"""R-05 费用标准：差旅费报销按城市/职级/天数比对费用标准。"""

from decimal import Decimal

from engine.base import EngineContext, EvidenceDraft, RuleFinding
from engine.registry import register

CATEGORY_MAP = (("住宿", "住宿"), ("交通", "交通"), ("餐饮", "餐饮"))
CITY_KEYWORDS = ("北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安")
UNIT_LABEL = {"晚": "晚", "天": "天", "人": "人"}


def _position_level(ctx: EngineContext) -> str:
    position = (ctx.applicant.position if ctx.applicant else "") or ""
    return "经理" if "经理" in position else "员工"


def _detect_city(ctx: EngineContext) -> str:
    text = " ".join(
        filter(
            None,
            [
                ctx.doc.description,
                ctx.doc.project,
                *(item.description for item in ctx.items),
                ctx.parsed_text(),
            ],
        )
    )
    for city in CITY_KEYWORDS:
        if city in text:
            return city
    return "通用"


@register("R-05")
def check_expense_standard(ctx: EngineContext, rule) -> list[RuleFinding]:
    if ctx.doc.doc_type != "差旅费报销":
        return []
    level = _position_level(ctx)
    city = _detect_city(ctx)
    findings: list[RuleFinding] = []

    for expense_type, category in CATEGORY_MAP:
        matched = [item for item in ctx.items if expense_type in item.expense_type]
        if not matched:
            continue
        standard = next(
            (
                std
                for std in ctx.standards
                if std.category == category and std.position_level == level and std.city == city
            ),
            None,
        ) or next(
            (
                std
                for std in ctx.standards
                if std.category == category and std.position_level == level and std.city == "通用"
            ),
            None,
        )
        if not standard:
            continue

        days = len({item.expense_date for item in matched}) or 1
        total = sum((item.amount for item in matched), Decimal("0.00"))
        limit = Decimal(str(standard.amount)) * days
        if total <= limit:
            continue

        unit = UNIT_LABEL.get(standard.unit, standard.unit or "天")
        evidences = [
            EvidenceDraft(
                evidence_type="expense_standard",
                snippet=(
                    f"{item.expense_type} {item.expense_date} {item.amount:.2f} 元"
                ),
                source="费用标准",
                page=1,
                confidence=95.0,
            )
            for item in matched
        ]
        findings.append(
            RuleFinding(
                rule_code="R-05",
                risk_level="mid",
                risk_desc=(
                    f"{category}费用合计 {total:.2f} 元，超出{city}{level}标准"
                    f"（{standard.amount:.2f} 元/{unit} × {days} {unit} = {limit:.2f} 元）"
                    f" {total - limit:.2f} 元。"
                ),
                score=15,
                risk_type="费用超标",
                evidences=evidences,
            )
        )
    return findings
