"""全链路 trace_id 与请求元信息。"""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_req_meta: ContextVar[dict] = ContextVar("req_meta", default={})


def get_trace_id() -> str:
    return _trace_id.get()


def get_req_meta() -> dict:
    return _req_meta.get()


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:16]
        token = _trace_id.set(trace_id)
        meta_token = _req_meta.set(
            {
                "user_agent": (request.headers.get("user-agent") or "")[:300],
                "ip": (request.client.host if request.client else "")[:45],
            }
        )
        try:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            _trace_id.reset(token)
            _req_meta.reset(meta_token)
