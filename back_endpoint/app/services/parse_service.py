"""附件解析：Vision 大模型结构化提取 + Mock 兜底，结果落 attachment_parse_result。

入口 `simulate_parse` 保持原有名称与调用方式不变（workflow 提交链 / 解析链直接复用），
内部改为调用 `ai_parser.parse_attachment_with_ai`：
- 配置了 Vision API 时识别真实票据；
- 未配置或识别失败时按文件名返回确定性 Mock 数据。
"""

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attachment, AttachmentParseResult, Document, DocumentItem
from app.services import ai_parser
from app.utils.storage import resolve_path
from app.utils.timefmt import now

logger = logging.getLogger(__name__)


def _confidence_of(fields: list[dict], fallback: float) -> int:
    values = []
    for field in fields:
        try:
            values.append(float(field.get("confidence", 0) or 0))
        except (TypeError, ValueError):
            continue
    if not values:
        return int(round(fallback))
    return max(1, min(99, int(round(sum(values) / len(values)))))


def simulate_parse(db: Session, att: Attachment, doc: Document) -> AttachmentParseResult:
    items = db.execute(
        select(DocumentItem).where(DocumentItem.document_id == doc.id).order_by(DocumentItem.item_no)
    ).scalars().all()
    total = sum((item.amount for item in items), Decimal("0.00"))

    existing = db.execute(
        select(AttachmentParseResult).where(AttachmentParseResult.attachment_id == att.id)
    ).scalar_one_or_none()

    if "损坏" in att.file_name:
        att.parse_status = "failed"
        if existing:
            existing.parse_status = "failed"
            existing.error_msg = "文件解析失败"
            existing.parse_time = now()
            return existing
        result = AttachmentParseResult(
            attachment_id=att.id,
            parse_status="failed",
            parse_type="ocr",
            result_json=None,
            confidence=None,
            error_msg="文件解析失败",
            parse_time=now(),
        )
        db.add(result)
        return result

    path = resolve_path(att.file_url)
    try:
        parsed = ai_parser.parse_attachment_with_ai(
            str(path) if path else att.file_name,
            file_name=att.file_name,
            expected_total=total,
            project=doc.project,
        )
    except Exception:  # 解析层兜底：任何异常都不阻断提交链
        logger.exception("附件解析异常，标记为失败 attachment=%s", att.id)
        parsed = {"fields": [], "source": "failed", "confidence": 0.0}

    fields = [row for row in parsed.get("fields", []) if isinstance(row, dict)]
    overall = float(parsed.get("confidence") or 0)

    if parsed.get("source") == "failed" or not fields:
        att.parse_status = "failed"
        result = existing or AttachmentParseResult(
            attachment_id=att.id,
            parse_status="failed",
            parse_type="ocr",
            result_json=None,
            confidence=None,
            error_msg=None,
            parse_time=now(),
        )
        result.parse_status = "failed"
        result.error_msg = "文件解析失败"
        result.parse_time = now()
        if existing is None:
            db.add(result)
        return result

    parse_type = "ai" if parsed.get("source") == "ai" else "ocr"
    confidence = _confidence_of(fields, overall)

    att.parse_status = "parsed"
    if existing:
        existing.parse_status = "parsed"
        existing.parse_type = parse_type
        existing.result_json = fields
        existing.confidence = confidence
        existing.error_msg = None
        existing.parse_time = now()
        return existing

    result = AttachmentParseResult(
        attachment_id=att.id,
        parse_status="parsed",
        parse_type=parse_type,
        result_json=fields,
        confidence=confidence,
        error_msg=None,
        parse_time=now(),
    )
    db.add(result)
    db.flush()
    return result
