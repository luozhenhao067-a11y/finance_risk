"""规则执行器注册表。"""

from collections.abc import Callable

from engine.base import EngineContext, RuleFinding

LEVEL_MAP = {"medium": "mid", "mid": "mid", "high": "high", "low": "low"}

RULE_EXECUTORS: dict[str, Callable[[EngineContext, object], list[RuleFinding]]] = {}


def register(*rule_codes: str):
    def decorator(fn):
        for code in rule_codes:
            RULE_EXECUTORS[code] = fn
        return fn

    return decorator
