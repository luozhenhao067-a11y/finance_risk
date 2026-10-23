"""统一响应信封 {code, message, data, trace_id}。"""

from app.core.trace import get_trace_id


def envelope(code: int = 0, message: str = "success", data=None) -> dict:
    return {"code": code, "message": message, "data": data, "trace_id": get_trace_id()}


def ok(data=None, message: str = "success") -> dict:
    return envelope(0, message, data)
