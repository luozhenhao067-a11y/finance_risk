"""R-09 附件完整性：解析置信度偏低或必需附件缺失。"""

from engine.base import EngineContext, EvidenceDraft, RuleFinding
from engine.registry import register

INVOICE_CATEGORIES = ("费用报销", "差旅费报销")
CONTRACT_CATEGORIES = ("采购付款", "合同付款")


def _has_keyword(ctx: EngineContext, keywords: tuple[str, ...]) -> bool:
    return any(keyword in att.file_name for att in ctx.attachments for keyword in keywords)


@register("R-09")
def check_attachment_integrity(ctx: EngineContext, rule) -> list[RuleFinding]:
    threshold = float(rule.threshold) if rule.threshold is not None else 85.0
    findings: list[RuleFinding] = []

    low_confidence = []
    for att in ctx.attachments:
        result = ctx.parse_results.get(att.id)
        if not result or result.confidence is None:
            continue
        confidence = float(result.confidence)
        if confidence <= 1:
            confidence *= 100
        if confidence < threshold:
            low_confidence.append((att, confidence))
    if low_confidence:
        findings.append(
            RuleFinding(
                rule_code="R-09",
                risk_level="low",
                risk_desc=(
                    f"{len(low_confidence)} 个附件解析置信度低于 {threshold:.0f}%，"
                    f"识别结果可能不准确，请人工核对。"
                ),
                score=5,
                risk_type="附件识别质量",
                evidences=[
                    EvidenceDraft(
                        evidence_type="ocr_confidence",
                        snippet=f"{att.file_name} 解析置信度 {confidence:.2f}%",
                        source=att.file_name,
                        attachment_id=att.id,
                        confidence=confidence,
                    )
                    for att, confidence in low_confidence
                ],
            )
        )

    if ctx.doc.doc_type in INVOICE_CATEGORIES and not _has_keyword(ctx, ("发票", "票据")):
        findings.append(
            RuleFinding(
                rule_code="R-09",
                risk_level="low",
                risk_desc="报销类单据未上传发票类附件，请补充发票后重新提交。",
                score=5,
                risk_type="附件缺失",
                evidences=[
                    EvidenceDraft(
                        evidence_type="attachment_check",
                        snippet="未找到文件名含“发票/票据”的附件",
                        source="附件清单",
                        confidence=98.0,
                    )
                ],
            )
        )

    if ctx.doc.doc_type in CONTRACT_CATEGORIES and not _has_keyword(ctx, ("合同",)):
        findings.append(
            RuleFinding(
                rule_code="R-09",
                risk_level="low",
                risk_desc="采购/合同付款单据未上传合同附件，请补充合同后重新提交。",
                score=5,
                risk_type="附件缺失",
                evidences=[
                    EvidenceDraft(
                        evidence_type="attachment_check",
                        snippet="未找到文件名含“合同”的附件",
                        source="附件清单",
                        confidence=98.0,
                    )
                ],
            )
        )
    return findings
