"""内置规则执行器集合。"""

from engine.rules import (  # noqa: F401
    r01_amount_consistency,
    r05_expense_standard,
    r07_abnormal_consumption,
    r09_attachment_integrity,
    r10_duplicate_invoice,
    r11_ai_subject_consistency,
    r12_ai_consumption_anomaly,
)
