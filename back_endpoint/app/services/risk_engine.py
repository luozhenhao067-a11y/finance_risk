"""AI 增强风控判断：主体名称语义比对 + 消费异常检测。

本模块只负责“判断”，不直接写库；由 `engine/rules/r11_*`、`engine/rules/r12_*`
包装成 RuleFinding 后交给原规则引擎统一落库。

全部函数都具备确定性兜底：
- 配置了大模型：返回模型判断；
- 未配置或调用失败：使用名称归一化 / 1.5 倍历史均值阈值等规则判断。
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Document
from app.services import ai_client

logger = logging.getLogger(__name__)

# 同一角色组内才比对，避免把“买方”和“卖方”误判为不一致
BUYER_LABELS = ("甲方", "购买方", "发票抬头", "抬头", "付款方")
COUNTERPARTY_LABELS = ("乙方", "合同乙方", "销售方", "收款方", "供应商", "服务方", "开票方")

CITY_KEYWORDS = ("北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安")
REGION_PREFIXES = (
    "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安",
    "天津", "重庆", "苏州", "长沙", "郑州", "青岛", "宁波", "厦门", "合肥", "济南", "大连",
)
LEGAL_SUFFIXES = (
    "集团股份有限公司", "股份有限公司", "集团有限责任公司", "有限责任公司",
    "集团有限公司", "有限公司", "分公司", "公司", "集团",
)
INDUSTRY_SUFFIXES = (
    "网络科技", "信息科技", "科技有限公司", "科技", "信息技术", "贸易", "商贸",
    "服务", "实业", "控股", "企业",
)

_PARENTHESIS = re.compile(r"[（(][^）)]*[）)]")
_PUNCTUATION = re.compile(r"[\s\-_·.,，。、/\\:：'\"“”‘’]+")
_ANOMALY_THRESHOLD = 1.5


def run_risk_analysis(
    doc_id: int,
    trigger_type: str = "auto",
    triggered_by: str | None = None,
):
    """按单据 ID 执行完整风险分析（含 AI 增强规则）的便捷入口。

    主业务链仍复用 `engine.engine.run_risk_analysis(db, doc_id, ...)`，
    本函数供脚本 / 后台任务在无外部会话时直接调用。
    """
    from app.database import SessionLocal
    from engine.engine import run_risk_analysis as execute

    db = SessionLocal()
    try:
        analysis = execute(db, doc_id, trigger_type=trigger_type, triggered_by=triggered_by)
        db.commit()
        return analysis
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def normalize_company_name(name: str) -> str:
    """公司名归一化：去掉括号地名、前缀地名、法律与行业后缀。

    例：``北京云启科技有限公司`` / ``云启公司`` / ``云启科技（北京）有限公司``
    归一化后均为 ``云启``。
    """
    text = _PUNCTUATION.sub("", str(name or "").strip())
    text = _PARENTHESIS.sub("", text)
    changed = True
    while changed:
        changed = False
        for prefix in REGION_PREFIXES:
            if text.startswith(prefix) and len(text) > len(prefix):
                text = text[len(prefix) :]
                changed = True
                break
    changed = True
    while changed:
        changed = False
        for suffix in LEGAL_SUFFIXES:
            if text.endswith(suffix) and len(text) > len(suffix):
                text = text[: -len(suffix)]
                changed = True
                break
    changed = True
    while changed:
        changed = False
        for suffix in INDUSTRY_SUFFIXES:
            if text.endswith(suffix) and len(text) > len(suffix):
                text = text[: -len(suffix)]
                changed = True
                break
    return text.strip()


def names_are_consistent(first: str, second: str) -> bool:
    """规则兜底：归一化后相同，或一方包含另一方（长度至少 2）。"""
    left = normalize_company_name(first)
    right = normalize_company_name(second)
    if not left or not right:
        return False
    if left == right:
        return True
    if len(left) >= 2 and len(right) >= 2:
        return left in right or right in left
    return False


def _confidence(value: Any, default: float = 88.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number <= 1:
        number *= 100
    return round(max(0.0, min(100.0, number)), 2)


def _unique_by_core(observations: Iterable[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for row in observations:
        value = str(row.get("value") or "").strip()
        if not value:
            continue
        core = normalize_company_name(value) or value
        if core in seen:
            continue
        seen.add(core)
        result.append(row)
    return result


def evaluate_subject_consistency(
    groups: dict[str, list[dict]],
    context: str = "",
) -> dict:
    """判断合同主体 / 发票抬头 / 付款对象名称是否一致。

    groups 形如 ``{"购买方": [{"label","value","source"}], "收款方": [...]}``。
    返回 ``{"consistent", "confidence", "reason", "issues", "source"}``。
    """
    clean_groups = {
        group: _unique_by_core(rows)
        for group, rows in groups.items()
        if rows
    }
    clean_groups = {group: rows for group, rows in clean_groups.items() if len(rows) >= 2}
    if not clean_groups:
        return {
            "consistent": True,
            "confidence": 100.0,
            "reason": "可用于比对的同一角色名称不足两个，默认视为一致。",
            "issues": [],
            "source": "rule",
        }

    issues: list[dict] = []
    for group, rows in clean_groups.items():
        for index, first in enumerate(rows):
            for second in rows[index + 1 :]:
                if names_are_consistent(first["value"], second["value"]):
                    continue
                issues.append(
                    {
                        "group": group,
                        "first": first["value"],
                        "second": second["value"],
                    }
                )

    if ai_client.is_ai_enabled():
        prompt = (
            "你是财务风控审核专家。请判断下列同一角色组内的公司名称是否指向同一主体。\n"
            "注意：简称、全称、带/不带地区前缀、带/不带“有限公司/科技/集团”等后缀，"
            "均应视为一致。例如“北京云启科技”和“云启公司”一致。\n"
            "只比较同一角色组内部，不要跨组比较。\n"
            f"名称分组：{json.dumps(clean_groups, ensure_ascii=False)}\n"
            f"单据上下文：{context[:500]}\n"
            '返回严格 JSON：{"consistent": true/false, "confidence": 0-100, '
            '"reason": "不超过80字的判断理由"}'
        )
        payload = ai_client.chat_json(
            [
                {"role": "system", "content": "你是严谨的财务风控审核专家，只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=300,
        )
        if isinstance(payload, dict) and isinstance(payload.get("consistent"), bool):
            return {
                "consistent": payload["consistent"],
                "confidence": _confidence(payload.get("confidence")),
                "reason": str(payload.get("reason") or "").strip()
                or ("名称指向同一主体。" if payload["consistent"] else "名称疑似指向不同主体。"),
                "issues": issues,
                "source": "ai",
            }

    if issues:
        detail = "；".join(
            f"{row['group']}“{row['first']}”与“{row['second']}”" for row in issues[:3]
        )
        return {
            "consistent": False,
            "confidence": 88.0,
            "reason": f"名称归一化后核心主体不一致：{detail}。",
            "issues": issues,
            "source": "rule",
        }

    return {
        "consistent": True,
        "confidence": 90.0,
        "reason": "各角色组内公司名称归一化后指向同一主体。",
        "issues": [],
        "source": "rule",
    }


def detect_city(text: str) -> str:
    for city in CITY_KEYWORDS:
        if city in (text or ""):
            return city
    return "通用"


def historical_amount_stats(db: Session, doc: Document) -> dict:
    """同类型单据历史金额均值与样本量（排除当前单据与草稿）。"""
    average, count = db.execute(
        select(func.avg(Document.total_amount), func.count(Document.id)).where(
            Document.doc_type == doc.doc_type,
            Document.id != doc.id,
            Document.delete_flag == 0,
            Document.status.in_(("pending_approval", "approved", "completed", "returned")),
        )
    ).one()
    avg = _decimal(average)
    return {"avg": avg, "count": int(count or 0)}


def evaluate_consumption_anomaly(
    doc: Document,
    stats: dict,
    *,
    city: str,
    expense_types: list[str],
    threshold: float = _ANOMALY_THRESHOLD,
) -> dict:
    """结合单据金额、报销类型、历史均值与城市判断是否异常。

    返回 ``{"abnormal", "level", "confidence", "reason", "ratio", "source"}``。
    """
    amount = _decimal(doc.total_amount) or Decimal("0.00")
    average = stats.get("avg")
    count = int(stats.get("count") or 0)
    if average is None or average <= 0 or count < 3:
        return {
            "abnormal": False,
            "level": "none",
            "confidence": 0.0,
            "reason": "同类型历史样本不足 3 单，暂不做异常判断。",
            "ratio": 0.0,
            "source": "rule",
        }

    ratio = float(amount / average)
    if ai_client.is_ai_enabled():
        prompt = (
            "你是财务消费异常检测模型。请结合单据金额、报销类型、历史均值、样本量与城市，"
            "判断本单金额是否明显异常。参考阈值：当前金额超过历史均值 1.5 倍时通常可疑，"
            "但应结合城市消费水平与费用类型综合判断。\n"
            f"单据类型：{doc.doc_type}\n"
            f"单据标题：{doc.title}\n"
            f"本项目金额：{amount:.2f} 元\n"
            f"费用类型：{', '.join(expense_types) or '未填写'}\n"
            f"历史均值：{average:.2f} 元（样本 {count} 单）\n"
            f"当前城市：{city}\n"
            f"金额/均值倍数：{ratio:.2f}\n"
            f"单据说明：{(doc.description or '')[:300]}\n"
            '返回严格 JSON：{"abnormal": true/false, "level": "high|mid|low|none", '
            '"confidence": 0-100, "reason": "不超过80字的原因"}'
        )
        payload = ai_client.chat_json(
            [
                {"role": "system", "content": "你是严谨的财务消费异常检测模型，只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=300,
        )
        if isinstance(payload, dict) and isinstance(payload.get("abnormal"), bool):
            level = str(payload.get("level") or "none").lower()
            if level not in ("high", "mid", "low", "none"):
                level = "mid" if payload["abnormal"] else "none"
            if payload["abnormal"] and level == "none":
                level = "mid"
            return {
                "abnormal": payload["abnormal"],
                "level": level,
                "confidence": _confidence(payload.get("confidence"), 86.0),
                "reason": str(payload.get("reason") or "").strip()
                or f"金额为历史均值的 {ratio:.2f} 倍。",
                "ratio": round(ratio, 2),
                "source": "ai",
            }

    abnormal = ratio > threshold
    if abnormal:
        reason = f"金额为历史均值的 {ratio:.2f} 倍，超过 {threshold:.2f} 倍阈值。"
        level = "mid"
    else:
        reason = f"金额为历史均值的 {ratio:.2f} 倍，未超过 {threshold:.2f} 倍阈值。"
        level = "none"
    return {
        "abnormal": abnormal,
        "level": level,
        "confidence": 85.0,
        "reason": reason,
        "ratio": round(ratio, 2),
        "source": "rule",
    }
