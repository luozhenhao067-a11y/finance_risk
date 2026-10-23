"""多模态附件解析：优先调用 Vision 大模型，未配置或失败时返回逼真的 Mock 数据。

对外核心函数：
    parse_attachment_with_ai(file_path: str, ...) -> dict

返回结构（字段与契约 ParseField 对齐）::

    {
        "fields": [
            {"label": "发票号码", "value": "INV-20261012-0086",
             "confidence": 96, "page": 1, "position": "第1页 票面右上"},
            ...
        ],
        "page": 1,
        "position": "第1页 票面中部",
        "confidence": 94.5,
        "raw_text": "发票号码 ... 金额合计 ...",
        "source": "ai" | "mock",
    }

PDF 先按页渲染为图片（PyMuPDF 优先，pdf2image 兜底），再与普通图片一起转 Base64
发送给 Vision API。任何异常都静默降级为文件名 Mock，保证提交链不被阻断。
"""

from __future__ import annotations

import io
import logging
import zlib
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.config import settings
from app.services import ai_client

logger = logging.getLogger(__name__)

IMAGE_EXTS = ("png", "jpg", "jpeg")
MIME_BY_EXT = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
MAX_IMAGE_BYTES = 12 * 1024 * 1024

SYSTEM_PROMPT = (
    "你是财务单据 OCR 与结构化信息提取引擎。只输出严格 JSON，不要输出 Markdown、"
    "解释或多余文字。字段值必须来自票据原文；无法识别时填“未识别”。"
)

USER_PROMPT = """请识别附件中的财务票据，提取核心字段并返回 JSON：
{{
  "page": 1,
  "position": "字段整体所在位置描述",
  "confidence": 0-100 的整体置信度,
  "raw_text": "识别到的关键原文（不超过 300 字）",
  "fields": [
    {{
      "label": "字段名",
      "value": "字段值",
      "confidence": 0-100,
      "page": 1,
      "position": "第X页 位置描述"
    }}
  ]
}}

字段模板：
- 发票：发票号码、开票日期、购买方、销售方、金额合计、税额
- 行程单：行程单号、出发城市、到达城市、出行日期、交通费、承运方
- 合同/付款：合同编号、甲方、乙方、合同金额、本期应付、付款比例、收款方
金额请保留两位小数并带 ¥ 符号；日期使用 YYYY-MM-DD。

附件文件名：{file_name}
请直接输出 JSON。"""


def _money(value: Decimal | float | str | None, default: str = "¥3,860.00") -> str:
    if value in (None, ""):
        return default
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return default
    return f"¥{amount:,.2f}"


def _confidence(base: int, seed: str, spread: int = 3) -> int:
    offset = zlib.crc32(seed.encode("utf-8")) % (spread + 1)
    return max(1, min(99, base + offset))


def _field(
    label: str,
    value: str,
    confidence: int,
    page: int = 1,
    position: str = "第1页 票面中部",
) -> dict:
    return {
        "label": label,
        "value": value,
        "confidence": confidence,
        "page": page,
        "position": position,
    }


def _mock_result(
    file_name: str,
    expected_total: Decimal | float | str | None = None,
    project: str | None = None,
) -> dict:
    """按文件名生成确定性 Mock 数据；金额优先与单据金额保持一致。"""
    name = file_name or "未命名附件"
    supplier = f"{project}服务商" if project else "北京云启科技有限公司"
    amount = _money(expected_total, "¥3,860.00")
    page, position = 1, "第1页 票面中部"

    if any(keyword in name for keyword in ("发票", "票据")):
        fields = [
            _field("发票号码", "INV-20261012-0086", _confidence(96, name), page, "第1页 票面右上"),
            _field("开票日期", "2026-10-12", _confidence(94, name), page, "第1页 票面右上"),
            _field("购买方", "北京云启科技有限公司", _confidence(93, name), page, "第1页 抬头栏"),
            _field("销售方", supplier, _confidence(95, name), page, "第1页 销售方栏"),
            _field("金额合计", amount, _confidence(97, name), page, "第1页 价税合计栏"),
        ]
        raw_text = f"发票号码 INV-20261012-0086 开票日期 2026-10-12 销售方 {supplier} 金额合计 {amount}"
    elif any(keyword in name for keyword in ("行程单", "机票", "车票", "出差")):
        fields = [
            _field("行程单号", "TRIP-20261014-021", _confidence(95, name), page, "第1页 顶部编号"),
            _field("出发城市", "北京", _confidence(96, name), page, "第1页 行程栏"),
            _field("到达城市", "上海", _confidence(96, name), page, "第1页 行程栏"),
            _field("出行日期", "2026-10-14", _confidence(94, name), page, "第1页 行程栏"),
            _field("交通费", _money(expected_total, "¥1,280.00"), _confidence(96, name), page, "第1页 金额栏"),
            _field("承运方", "航旅纵横（北京）科技有限公司", _confidence(90, name), page, "第1页 承运方栏"),
        ]
        raw_text = f"行程单号 TRIP-20261014-021 北京 至 上海 2026-10-14 交通费 {amount}"
    elif "合同" in name:
        fields = [
            _field("合同编号", "HT-2026-1008", _confidence(95, name), page, "第1页 合同编号栏"),
            _field("甲方", "云启科技（北京）有限公司", _confidence(93, name), page, "第1页 甲方栏"),
            _field("乙方", supplier, _confidence(94, name), page, "第1页 乙方栏"),
            _field("合同金额", amount, _confidence(95, name), page, "第2页 金额条款"),
            _field("本期应付", amount, _confidence(93, name), 2, "第2页 付款条款"),
            _field("付款比例", "100%", _confidence(91, name), 2, "第2页 付款条款"),
        ]
        raw_text = f"合同编号 HT-2026-1008 甲方 云启科技（北京）有限公司 乙方 {supplier} 本期应付 {amount}"
    elif any(keyword in name for keyword in ("付款", "回单", "流水")):
        fields = [
            _field("付款单号", "PAY-20261015-006", _confidence(94, name), page, "第1页 顶部编号"),
            _field("付款方", "北京云启科技有限公司", _confidence(92, name), page, "第1页 付款方栏"),
            _field("收款方", supplier, _confidence(94, name), page, "第1页 收款方栏"),
            _field("付款金额", amount, _confidence(96, name), page, "第1页 金额栏"),
            _field("付款日期", "2026-10-15", _confidence(93, name), page, "第1页 日期栏"),
        ]
        raw_text = f"付款单号 PAY-20261015-006 收款方 {supplier} 付款金额 {amount}"
    else:
        fields = [
            _field("文件类型", "其他财务附件", _confidence(90, name), page, "第1页 顶部"),
            _field("金额合计", amount, _confidence(88, name), page, "第1页 金额栏"),
            _field("识别说明", "Mock 解析：未匹配到发票/行程单/合同模板", _confidence(85, name), page, "第1页 备注"),
        ]
        raw_text = f"{name} 金额合计 {amount}"

    return {
        "fields": fields,
        "page": page,
        "position": position,
        "confidence": float(_confidence(91, name)),
        "raw_text": raw_text,
        "source": "mock",
    }


def _pdf_images(path: Path) -> list[bytes] | None:
    """PDF 前 N 页转 PNG。PyMuPDF 优先，pdf2image 兜底。"""
    pages: list[bytes] = []
    try:
        try:
            import pymupdf as fitz  # PyMuPDF 新版包名
        except ImportError:
            import fitz  # PyMuPDF 旧版包名

        with fitz.open(path) as document:
            for index, page in enumerate(document):
                if index >= max(1, settings.ai_max_pages):
                    break
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                pages.append(pixmap.tobytes("png"))
        return pages or None
    except ImportError:
        pass
    except Exception as exc:  # 文件损坏 / 加密等
        logger.warning("PyMuPDF 解析 PDF 失败 %s: %s", path.name, exc)
        return None

    try:
        from pdf2image import convert_from_path

        images = convert_from_path(
            str(path), first_page=1, last_page=max(1, settings.ai_max_pages), fmt="png"
        )
        for image in images:
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            pages.append(buffer.getvalue())
        return pages or None
    except ImportError:
        logger.warning("未安装 PyMuPDF/pdf2image，PDF 附件将使用 Mock 解析")
        return None
    except Exception as exc:
        logger.warning("pdf2image 解析 PDF 失败 %s: %s", path.name, exc)
        return None


def _load_images(file_path: str) -> list[tuple[bytes, str]] | None:
    path = Path(file_path)
    if not path.is_file():
        return None
    suffix = path.suffix.lower().lstrip(".")
    try:
        if suffix == "pdf":
            pages = _pdf_images(path)
            return [(page, "image/png") for page in pages] if pages else None
        if suffix in IMAGE_EXTS:
            raw = path.read_bytes()
            if not raw or len(raw) > MAX_IMAGE_BYTES:
                return None
            return [(raw, MIME_BY_EXT.get(suffix, "image/png"))]
    except OSError as exc:
        logger.warning("读取附件失败 %s: %s", file_path, exc)
    return None


def _normalize_confidence(value, default: float = 90.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number <= 1:
        number *= 100
    return round(max(0.0, min(100.0, number)), 2)


def _normalize_fields(payload) -> list[dict]:
    if isinstance(payload, dict):
        rows = [
            {"label": key, "value": value}
            for key, value in payload.items()
            if value not in (None, "")
        ]
    elif isinstance(payload, list):
        rows = payload
    else:
        return []

    fields: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or row.get("field") or row.get("name") or "").strip()
        value = row.get("value", row.get("text", row.get("content", "")))
        if not label or value in (None, ""):
            continue
        try:
            page = int(row.get("page") or 1)
        except (TypeError, ValueError):
            page = 1
        fields.append(
            {
                "label": label,
                "value": str(value).strip(),
                "confidence": _normalize_confidence(row.get("confidence")),
                "page": max(1, page),
                "position": str(row.get("position") or "").strip() or "第1页 未标注位置",
            }
        )
    return fields


def _parse_with_vision(file_path: str, file_name: str) -> dict | None:
    images = _load_images(file_path)
    if not images:
        return None
    text = ai_client.chat_vision(
        USER_PROMPT.format(file_name=file_name),
        images,
        system_prompt=SYSTEM_PROMPT,
    )
    payload = ai_client.extract_json(text)
    if not isinstance(payload, dict):
        logger.warning("Vision 返回内容无法解析为 JSON：%s", (text or "")[:200])
        return None
    fields = _normalize_fields(payload.get("fields"))
    if not fields:
        return None
    try:
        page = max(1, int(payload.get("page") or 1))
    except (TypeError, ValueError):
        page = 1
    return {
        "fields": fields,
        "page": page,
        "position": str(payload.get("position") or "").strip() or "第1页 未标注位置",
        "confidence": _normalize_confidence(payload.get("confidence"), 90.0),
        "raw_text": str(payload.get("raw_text") or "").strip(),
        "source": "ai",
    }


def parse_attachment_with_ai(
    file_path: str,
    *,
    file_name: str | None = None,
    expected_total: Decimal | float | str | None = None,
    project: str | None = None,
) -> dict:
    """解析发票 / 行程单 / 合同等附件。

    - 配置了 `AI_VISION_MODEL` 且文件可读：调用 Vision API，返回真实识别结果；
    - 未配置、文件缺失、网络失败或返回格式异常：按文件名返回 Mock 数据。
    """
    name = (file_name or Path(file_path).name or "未命名附件").strip()
    if "损坏" in name:
        return {
            "fields": [],
            "page": 1,
            "position": "",
            "confidence": 0.0,
            "raw_text": "",
            "source": "failed",
        }

    if ai_client.is_vision_enabled():
        try:
            parsed = _parse_with_vision(file_path, name)
            if parsed:
                return parsed
        except Exception:  # 防御性兜底：解析失败不影响主链路
            logger.exception("Vision 解析异常，降级为 Mock：%s", name)

    return _mock_result(name, expected_total, project)
