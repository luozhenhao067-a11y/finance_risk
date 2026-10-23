"""CSV 导出（带 BOM，Excel 中文不乱码）。"""

import csv
import io
from urllib.parse import quote

from fastapi.responses import StreamingResponse


def csv_stream(rows: list[list], headers: list[str], filename: str) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    data = ("﻿" + buffer.getvalue()).encode("utf-8")
    return StreamingResponse(
        iter([data]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
