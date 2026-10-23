"""FastAPI 应用入口。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.core.errors import BizError, ErrorCode
from app.core.response import envelope, ok
from app.core.trace import TraceMiddleware
from app.database import engine
from app.migrate import run_migrations

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_migrations(engine)
    settings.files_dir.mkdir(parents=True, exist_ok=True)
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    from app.services import ai_client

    logger.info(
        "startup complete: db=%s storage=%s ai=%s",
        settings.db_name,
        settings.storage_dir,
        ai_client.ai_status(),
    )
    yield


app = FastAPI(title="财务单据智能风险审核系统 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Trace-Id", "Content-Disposition"],
)
app.add_middleware(TraceMiddleware)


@app.exception_handler(BizError)
async def biz_error_handler(_: Request, exc: BizError):
    return JSONResponse(
        status_code=exc.http_status,
        content=envelope(exc.code, exc.message, exc.data),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    loc = ".".join(str(item) for item in first.get("loc", []) if item != "body")
    message = f"参数错误：{loc} {first.get('msg', '')}".strip()
    return JSONResponse(status_code=200, content=envelope(ErrorCode.PARAM_ERROR, message))


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: Request, exc: StarletteHTTPException):
    if exc.status_code == 401:
        code, message = ErrorCode.UNAUTHORIZED, "未登录或凭证已失效"
    elif exc.status_code == 403:
        code, message = ErrorCode.FORBIDDEN, "无权执行该操作"
    elif exc.status_code == 404:
        code, message = ErrorCode.DOC_NOT_FOUND, "资源不存在"
    else:
        code, message = ErrorCode.SYSTEM_ERROR, str(exc.detail)
    return JSONResponse(status_code=exc.status_code, content=envelope(code, message))


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception):
    logger.exception("unhandled error: %s", exc)
    return JSONResponse(
        status_code=500, content=envelope(ErrorCode.SYSTEM_ERROR, "系统繁忙，请稍后重试")
    )


from app.routers import (  # noqa: E402
    admin as admin_router,
    ai_chat as ai_chat_router,
    approvals as approvals_router,
    attachments as attachments_router,
    auth as auth_router,
    dashboard as dashboard_router,
    documents as documents_router,
    logs as logs_router,
    notifications as notifications_router,
    reports as reports_router,
    risks as risks_router,
)

API_PREFIX = "/api/v1"
for router_module in (
    auth_router,
    dashboard_router,
    notifications_router,
    documents_router,
    attachments_router,
    ai_chat_router,
    approvals_router,
    risks_router,
    reports_router,
    logs_router,
    admin_router,
):
    app.include_router(router_module.router, prefix=API_PREFIX)


@app.get("/api/v1/health")
def health():
    return ok({"status": "ok"})
