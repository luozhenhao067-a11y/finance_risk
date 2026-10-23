"""业务错误码与异常。"""


class ErrorCode:
    OK = 0
    PARAM_ERROR = 40001
    UNAUTHORIZED = 40101
    LOGIN_FAILED = 40102
    ACCOUNT_LOCKED = 40103
    FORBIDDEN = 40301
    DATA_SCOPE_DENIED = 40302
    DOC_NOT_FOUND = 40401
    ATTACHMENT_NOT_FOUND = 40402
    TASK_NOT_FOUND = 40403
    STATE_CONFLICT = 40901
    TASK_HANDLED = 40902
    VERSION_CONFLICT = 40903
    SYSTEM_ERROR = 50001


class BizError(Exception):
    """业务异常：默认 HTTP 200 + 业务码，认证类可用 http_status=401。"""

    def __init__(self, code: int, message: str, data=None, http_status: int = 200):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data
        self.http_status = http_status


def bad_request(message: str, data=None) -> BizError:
    return BizError(ErrorCode.PARAM_ERROR, message, data)


def unauthorized(message: str = "未登录或凭证已失效") -> BizError:
    return BizError(ErrorCode.UNAUTHORIZED, message, http_status=401)


def forbidden(message: str = "无权执行该操作") -> BizError:
    return BizError(ErrorCode.FORBIDDEN, message)


def data_scope_denied(message: str = "无权访问该数据") -> BizError:
    return BizError(ErrorCode.DATA_SCOPE_DENIED, message)


def not_found(message: str = "单据不存在", code: int = ErrorCode.DOC_NOT_FOUND) -> BizError:
    return BizError(code, message)


def state_conflict(message: str = "单据当前状态不允许该操作") -> BizError:
    return BizError(ErrorCode.STATE_CONFLICT, message)


def version_conflict(latest_version: int) -> BizError:
    return BizError(
        ErrorCode.VERSION_CONFLICT,
        "单据已被他人修改，请刷新后重试",
        data={"version": latest_version},
    )
