"""JWT、密码校验、登录失败限流。"""

import threading
from datetime import datetime, timedelta

import bcrypt
import jwt

from app.config import settings
from app.core.errors import ErrorCode, BizError, unauthorized


def create_token(user_id: int, username: str) -> str:
    now = datetime.now()
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise unauthorized()
    except Exception:
        raise unauthorized()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


class LoginLimiter:
    """进程内登录失败计数：5 次失败锁定 15 分钟（uvicorn 单进程部署）。"""

    def __init__(self):
        self._fails: dict[str, int] = {}
        self._locked_until: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def check(self, username: str) -> None:
        with self._lock:
            until = self._locked_until.get(username)
            if until and until > datetime.now():
                raise BizError(ErrorCode.ACCOUNT_LOCKED, "账号已锁定，请15分钟后重试")
            if until and until <= datetime.now():
                self._locked_until.pop(username, None)
                self._fails.pop(username, None)

    def on_fail(self, username: str) -> None:
        with self._lock:
            fails = self._fails.get(username, 0) + 1
            self._fails[username] = fails
            if fails >= settings.login_max_fails:
                self._locked_until[username] = datetime.now() + timedelta(minutes=settings.login_lock_minutes)
                raise BizError(ErrorCode.ACCOUNT_LOCKED, "账号已锁定，请15分钟后重试")
        raise BizError(ErrorCode.LOGIN_FAILED, "用户名或密码错误")

    def on_success(self, username: str) -> None:
        with self._lock:
            self._fails.pop(username, None)
            self._locked_until.pop(username, None)


login_limiter = LoginLimiter()
