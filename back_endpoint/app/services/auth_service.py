"""认证服务。"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import AuthUser, _load_user
from app.core.errors import bad_request
from app.core.security import create_token, login_limiter, verify_password
from app.models import User


def login(db: Session, username: str, password: str) -> dict:
    username = (username or "").strip()
    password = password or ""
    if not username or not password:
        raise bad_request("请输入用户名和密码")

    login_limiter.check(username)

    user = db.execute(
        select(User).where(or_(User.username == username, User.real_name == username)).limit(1)
    ).scalar_one_or_none()
    if not user or user.status != 1:
        login_limiter.on_fail(username)

    if not verify_password(password, user.password):
        login_limiter.on_fail(username)

    login_limiter.on_success(username)
    auth = _load_user(db, user.id)
    token = create_token(user.id, user.username)
    return {"token": token, "user": auth.to_dict()}


def me(auth: AuthUser) -> dict:
    return {"user": auth.to_dict(), "permissions": auth.perm_codes}
