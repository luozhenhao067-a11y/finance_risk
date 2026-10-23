"""后台异步链：submitted → analyzing → pending_approval。

由 BackgroundTasks 调用，必须使用新的 SessionLocal（请求会话已关闭）。
无论解析/规则分析成败，单据都推进到 pending_approval。
"""

import logging
import time

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Attachment, Document
from app.services import approval_service, log_service, notification_service, parse_service
from app.services.state_machine import NODE_NAMES, transition
from engine.engine import mark_failed, run_analysis

logger = logging.getLogger(__name__)

PARSE_DELAY = 0.25
MAX_PARSE_DELAY = 2.5
ANALYSIS_RETRIES = 3


def _load_attachments(db, doc_id: int) -> list[Attachment]:
    return db.execute(
        select(Attachment).where(Attachment.document_id == doc_id).order_by(Attachment.id)
    ).scalars().all()


def _finish(db, doc_id: int) -> None:
    """幂等收尾：analyzing → pending_approval，创建首审批节点任务。"""
    doc = db.get(Document, doc_id)
    if not doc or doc.status != "analyzing":
        return
    transition(doc, "finish_analysis", next_node=NODE_NAMES[0])
    flow = approval_service.get_flow(db, doc.id)
    if flow is None:
        flow = approval_service.reset_flow(db, doc)
    task = approval_service.current_pending_task(db, doc)
    if task is None:
        approval_service.create_task(db, flow, doc, NODE_NAMES[0])
    notification_service.notify(
        db, doc.applicant_id, doc.id, f"{doc.doc_no} 风险分析完成", "单据已进入审批流程", "system"
    )
    db.commit()


def submit_chain(doc_id: int) -> None:
    db = SessionLocal()
    try:
        doc = db.get(Document, doc_id)
        if not doc or doc.status != "submitted":
            return
        transition(doc, "start_analysis")
        log_service.record(
            db, "开始风险分析", doc_id=doc.id, detail="系统开始解析附件并执行风险规则"
        )
        db.commit()

        elapsed = 0.0
        for att in _load_attachments(db, doc_id):
            try:
                parse_service.simulate_parse(db, att, doc)
                db.commit()
            except Exception:
                logger.exception("附件解析失败 attachment=%s", att.id)
                db.rollback()
            delay = min(PARSE_DELAY, max(0.0, MAX_PARSE_DELAY - elapsed))
            if delay:
                time.sleep(delay)
                elapsed += delay

        analysis = None
        for attempt in range(ANALYSIS_RETRIES):
            try:
                analysis = run_analysis(db, doc_id, trigger_type="auto", triggered_by="规则引擎")
                db.commit()
                break
            except Exception:
                logger.exception("风险分析失败 doc=%s attempt=%s", doc_id, attempt + 1)
                db.rollback()
                time.sleep(0.3 * (attempt + 1))

        if analysis is None:
            try:
                mark_failed(db, doc_id)
                db.commit()
            except Exception:
                logger.exception("标记分析失败出错 doc=%s", doc_id)
                db.rollback()

        db.refresh(doc)
        if analysis is not None:
            log_service.record(
                db,
                "风险分析完成",
                doc_id=doc.id,
                detail=(
                    f"整体风险等级 {analysis.overall_level}，"
                    f"共 {analysis.risk_count} 项风险（高 {analysis.high_count} / 中 {analysis.mid_count} / 低 {analysis.low_count}）"
                ),
            )
        else:
            log_service.record(db, "风险分析完成", doc_id=doc.id, detail="风险分析失败，已转人工复核")
    except Exception:
        logger.exception("提交链异常 doc=%s", doc_id)
        db.rollback()
    finally:
        try:
            _finish(db, doc_id)
        except Exception:
            logger.exception("收尾进入审批失败 doc=%s", doc_id)
            db.rollback()
        finally:
            db.close()


def parse_chain(attachment_id: int) -> None:
    db = SessionLocal()
    try:
        att = db.get(Attachment, attachment_id)
        if not att:
            return
        doc = db.get(Document, att.document_id)
        if not doc:
            return
        parse_service.simulate_parse(db, att, doc)
        db.commit()
    except Exception:
        logger.exception("附件解析失败 attachment=%s", attachment_id)
        db.rollback()
    finally:
        db.close()


def rerun_chain(doc_id: int, reason: str, triggered_by: str) -> None:
    db = SessionLocal()
    try:
        doc = db.get(Document, doc_id)
        if not doc:
            return
        analysis = run_analysis(db, doc_id, trigger_type="manual", triggered_by=triggered_by)
        if analysis:
            log_service.record(
                db, "重新分析", doc_id=doc_id, detail=f"{reason}；结果 {analysis.overall_level}，{analysis.risk_count} 项风险"
            )
        db.commit()
    except Exception:
        logger.exception("重新分析失败 doc=%s", doc_id)
        db.rollback()
    finally:
        db.close()
