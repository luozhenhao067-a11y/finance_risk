"""认证请求体。"""

from pydantic import BaseModel


class LoginIn(BaseModel):
    username: str = ""
    password: str = ""
    remember: bool | None = None
