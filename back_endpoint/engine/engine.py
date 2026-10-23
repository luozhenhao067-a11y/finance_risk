"""风险分析执行入口。

run_risk_analysis 只依赖数据库数据，结果写入 risk_analysis / risk_item / risk_evidence，
并回写 document.risk_level / risk_count。单条规则异常不影响其它规则。

执行顺序：先跑传统 if-else 规则（R-01/R-05/R-07/R-09/R-10），
最后追加 AI 增强规则（R-11 主体名称语义一致性、R-12 消费异常检测），
AI 规则未配置大模型时自动使用规则兜底，不会阻断分析。
"""

import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

import engine.rules  # noqa: F401  导入即注册全部规则
from app.models import (
    Attachment,
    AttachmentParseResult,
    Document,
    DocumentItem,
    ExpenseStandard,
    RiskAnalysis,
    RiskEvidence,
    RiskItem,
    RiskRule,
    User,
    Vendor,
)
from app.utils.ids import next_analysis_no
from app.utils.timefmt import now
from engine.base import EngineContext, RuleFinding
from engine.registry import LEVEL_MAP, RULE_EXECUTORS

logger = logging.getLogger(__name__)

AI_RULE_CODES = ("R-11", "R-12")
SCORE_BY_LEVEL = {"high": 30, "mid": 15, "low": 5}
RECOMMENDATION = {
    "high": ("manual_review", "人工复核"),
    "mid": ("supplement", "补充材料"),
    "low": ("pass", "建议通过"),
    "none": ("pass", "建议通过"),
}


def _load_context(db: Session, doc: Document) -> EngineContext:
    items = db.execute(
        select(DocumentItem).where(DocumentItem.document_id == doc.id).order_by(DocumentItem.item_no)
    ).scalars().all()
    attachments = db.execute(
        select(Attachment).where(Attachment.document_id == doc.id).order_by(Attachment.id)
    ).scalars().all()
    parse_rows = db.execute(
        select(AttachmentParseResult).where(
            AttachmentParseResult.attachment_id.in_([att.id for att in attachments])
        )
    ).scalars().all() if attachments else []
    standards = db.execute(
        select(ExpenseStandard).where(ExpenseStandard.enabled == 1)
    ).scalars().all()
    vendors = db.execute(select(Vendor)).scalars().all()
    applicant = db.get(User, doc.applicant_id)
    return EngineContext(
        db=db,
        doc=doc,
        applicant=applicant,
        items=list(items),
        attachments=list(attachments),
        parse_results={row.attachment_id: row for row in parse_rows},
        standards=list(standards),
        vendors=list(vendors),
    )


def _reset_analysis(db: Session, doc: Document, trigger_type: str, triggered_by: str | None) -> RiskAnalysis:
    analysis = db.execute(
        select(RiskAnalysis).where(
            RiskAnalysis.document_id == doc.id, RiskAnalysis.doc_version == doc.version
        )
    ).scalar_one_or_none()
    if analysis:
        db.execute(delete(RiskItem).where(RiskItem.analysis_id == analysis.id))
        analysis.status = "analyzing"
        analysis.start_time = now()
        analysis.end_time = None
        analysis.analyzed_at = None
        analysis.trigger_type = trigger_type
        analysis.triggered_by = triggered_by
        analysis.summary = None
        return analysis
    analysis = RiskAnalysis(
        document_id=doc.id,
        doc_version=doc.version,
        analysis_no=next_analysis_no(db, RiskAnalysis.analysis_no, now().date()),
        risk_score=0,
        risk_level="low",
        overall_level="none",
        high_count=0,
        mid_count=0,
        low_count=0,
        recommendation="pass",
        recommendation_label="建议通过",
        trigger_type=trigger_type,
        triggered_by=triggered_by,
        analyzed_at=None,
        risk_count=0,
        status="analyzing",
        analyzer="规则引擎",
        start_time=now(),
        end_time=None,
        summary=None,
    )
    db.add(analysis)
    db.flush()
    return analysis


def _enabled_rules(db: Session) -> list[RiskRule]:
    return db.execute(
        select(RiskRule)
        .where(RiskRule.enabled == 1, RiskRule.risk_level != "blocking")
        .order_by(RiskRule.id)
    ).scalars().all()


def _write_findings(db: Session, analysis: RiskAnalysis, rules: list[RiskRule], findings: list[RuleFinding]) -> None:
    rule_map = {rule.rule_code: rule for rule in rules}
    moment = now()
    for finding in findings:
        rule = rule_map.get(finding.rule_code)
        if not rule:
            continue
        level = LEVEL_MAP.get(finding.risk_level, "low")
        item = RiskItem(
            analysis_id=analysis.id,
            rule_id=rule.id,
            risk_type=finding.risk_type or rule.rule_type,
            risk_level=level,
            risk_desc=finding.risk_desc,
            score=int(finding.score or SCORE_BY_LEVEL.get(level, 5)),
            status="open",
            handled_by=None,
            handled_at=None,
            handle_opinion=None,
            created_at=moment,
        )
        db.add(item)
        db.flush()
        for evidence in finding.evidences:
            db.add(
                RiskEvidence(
                    risk_item_id=item.id,
                    evidence_type=evidence.evidence_type,
                    evidence_content=_json_content(evidence),
                    source=evidence.source,
                    attachment_id=evidence.attachment_id,
                    created_at=moment,
                )
            )


def _json_content(evidence) -> str:
    import json

    return json.dumps(
        {
            "snippet": evidence.snippet,
            "page": evidence.page,
            "confidence": evidence.confidence,
        },
        ensure_ascii=False,
    )


def run_risk_analysis(
    db: Session,
    doc_id: int,
    trigger_type: str = "auto",
    triggered_by: str | None = None,
) -> RiskAnalysis | None:
    doc = db.get(Document, doc_id)
    if not doc or doc.delete_flag:
        return None

    analysis = _reset_analysis(db, doc, trigger_type, triggered_by)
    db.flush()

    context = _load_context(db, doc)
    rules = _enabled_rules(db)
    # 传统规则先执行，AI 增强规则统一放到最后，避免 AI 判断影响基础规则顺序
    ordered_rules = sorted(
        rules, key=lambda item: (item.rule_code in AI_RULE_CODES, item.id)
    )
    findings: list[RuleFinding] = []
    for rule in ordered_rules:
        executor = RULE_EXECUTORS.get(rule.rule_code)
        if not executor:
            continue
        try:
            findings.extend(executor(context, rule) or [])
        except Exception:
            logger.exception("规则 %s 执行失败", rule.rule_code)
            continue

    _write_findings(db, analysis, rules, findings)

    high = sum(1 for item in findings if LEVEL_MAP.get(item.risk_level) == "high")
    mid = sum(1 for item in findings if LEVEL_MAP.get(item.risk_level) == "mid")
    low = sum(1 for item in findings if LEVEL_MAP.get(item.risk_level) == "low")
    overall = "high" if high else "mid" if mid else "low" if low else "none"
    recommendation, label = RECOMMENDATION[overall]

    analysis.status = "completed"
    analysis.overall_level = overall
    analysis.risk_level = overall
    analysis.high_count = high
    analysis.mid_count = mid
    analysis.low_count = low
    analysis.risk_count = len(findings)
    analysis.risk_score = min(100, sum(int(item.score or SCORE_BY_LEVEL.get(LEVEL_MAP.get(item.risk_level), 5)) for item in findings))
    analysis.recommendation = recommendation
    analysis.recommendation_label = label
    analysis.analyzed_at = now()
    analysis.end_time = now()
    if findings:
        analysis.summary = (
            f"共发现 {len(findings)} 项风险：高风险 {high} 项、中风险 {mid} 项、低风险 {low} 项。"
        )
    else:
        analysis.summary = "未发现明显风险，建议通过。"

    doc.risk_level = overall
    doc.risk_count = len(findings)
    doc.updated_at = now()
    db.flush()
    return analysis


# 兼容既有调用方（workflow / risk_service 使用旧名称）
run_analysis = run_risk_analysis


def mark_failed(db: Session, doc_id: int, reason: str = "analysis_failed") -> RiskAnalysis | None:
    doc = db.get(Document, doc_id)
    if not doc:
        return None
    analysis = db.execute(
        select(RiskAnalysis).where(
            RiskAnalysis.document_id == doc.id, RiskAnalysis.doc_version == doc.version
        )
    ).scalar_one_or_none()
    if not analysis:
        analysis = RiskAnalysis(
            document_id=doc.id,
            doc_version=doc.version,
            analysis_no=next_analysis_no(db, RiskAnalysis.analysis_no, now().date()),
            risk_score=0,
            risk_level="low",
            risk_count=0,
            trigger_type="auto",
            status="failed",
            start_time=now(),
        )
        db.add(analysis)
    analysis.status = "failed"
    analysis.summary = reason
    analysis.analyzed_at = now()
    analysis.end_time = now()
    db.flush()
    return analysis
