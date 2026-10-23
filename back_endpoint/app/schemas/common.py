"""通用请求体。"""

from pydantic import BaseModel, Field


class ReasonIn(BaseModel):
    reason: str | None = Field(default=None, max_length=200)
