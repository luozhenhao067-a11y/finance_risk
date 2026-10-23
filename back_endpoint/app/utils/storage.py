"""本地附件存储与文件元信息。"""

import re
import uuid
from pathlib import Path

from app.config import settings

MIME_BY_EXT = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


def ext_of(file_name: str) -> str:
    return file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""


def mime_of(file_name: str) -> str:
    return MIME_BY_EXT.get(ext_of(file_name), "application/octet-stream")


def file_type_of(file_name: str) -> str:
    return "pdf" if ext_of(file_name) == "pdf" else "image"


def parse_size_label(label: str | None, size_bytes: int = 0) -> int:
    """'860KB' / '1.2MB' → KB 整数；无标签时按字节折算。"""
    if label:
        match = re.match(r"^\s*([\d.]+)\s*(KB|MB|GB|B)?\s*$", label, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = (match.group(2) or "B").upper()
            factor = {"B": 1 / 1024, "KB": 1, "MB": 1024, "GB": 1024 * 1024}[unit]
            return max(1, int(round(value * factor)))
    return max(1, int(round(size_bytes / 1024)))


def size_label(kb: int) -> str:
    if kb >= 1024:
        return f"{kb / 1024:.1f}MB"
    return f"{kb}KB"


def save_upload(doc_no: str, version: int, file_name: str, content: bytes) -> tuple[str, Path]:
    folder = settings.files_dir / doc_no / f"v{version}"
    folder.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex[:8]}_{file_name}"
    path = folder / stored_name
    path.write_bytes(content)
    rel_url = f"/files/{doc_no}/v{version}/{stored_name}"
    return rel_url, path


def resolve_path(rel_url: str) -> Path | None:
    if not rel_url:
        return None
    candidate = (settings.storage_dir / rel_url.lstrip("/")).resolve()
    try:
        candidate.relative_to(settings.storage_dir.resolve())
    except ValueError:
        return None
    return candidate if candidate.exists() else None


def delete_file(rel_url: str) -> None:
    path = resolve_path(rel_url)
    if path:
        path.unlink(missing_ok=True)
