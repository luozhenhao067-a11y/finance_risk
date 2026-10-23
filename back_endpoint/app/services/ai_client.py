"""统一大模型调用封装（OpenAI 兼容 /chat/completions）。

设计原则：
1. 所有对外部大模型的调用都从这里发出，业务层只依赖 `chat_completion` / `chat_json` / `chat_vision`。
2. 任何失败（未配置 Key、网络异常、超时、返回格式错误）都返回 `None`，绝不向上抛异常，
   由调用方切换到规则 / 模板 / Mock 兜底，保证前后端联调与演示不中断。
3. 兼容 DeepSeek、通义千问、OpenAI 等 OpenAI 格式接口；只需在 .env 配置
   `AI_API_KEY`、`AI_BASE_URL`、`AI_MODEL`（视觉能力另配 `AI_VISION_MODEL`）。
"""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any, Iterable

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S | re.I)


def is_ai_enabled() -> bool:
    """文本模型是否可用。"""
    return settings.ai_enabled


def is_vision_enabled() -> bool:
    """多模态模型是否可用。"""
    return settings.ai_vision_enabled


def ai_status() -> dict:
    """返回脱敏后的 AI 配置状态，供健康检查 / 排查使用。"""
    return {
        "text_enabled": is_ai_enabled(),
        "vision_enabled": is_vision_enabled(),
        "model": settings.ai_model if is_ai_enabled() else "",
        "vision_model": settings.ai_vision_model if is_vision_enabled() else "",
        "base_url": settings.ai_base_url if is_ai_enabled() else "",
    }


def _post(
    messages: list[dict],
    *,
    api_key: str,
    base_url: str,
    model: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: float | None = None,
) -> str | None:
    if not api_key or not model:
        return None
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": settings.ai_temperature if temperature is None else temperature,
        "max_tokens": settings.ai_max_tokens if max_tokens is None else max_tokens,
        "stream": False,
    }
    try:
        with httpx.Client(timeout=timeout or settings.ai_timeout_seconds) as client:
            response = client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.status_code >= 400:
            logger.warning(
                "AI 请求失败 status=%s body=%s",
                response.status_code,
                response.text[:300],
            )
            return None
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):  # 部分兼容接口返回分段内容
            content = "".join(
                str(part.get("text", ""))
                for part in content
                if isinstance(part, dict)
            )
        text = str(content or "").strip()
        return text or None
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning("AI 请求异常：%s", exc)
        return None


def chat_completion(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: float | None = None,
) -> str | None:
    """文本对话补全；未配置或失败返回 None。"""
    if not is_ai_enabled():
        return None
    return _post(
        messages,
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url,
        model=model or settings.ai_model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def chat_vision(
    prompt: str,
    images: Iterable[tuple[bytes, str]],
    *,
    system_prompt: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    timeout: float | None = None,
) -> str | None:
    """多模态对话补全。images 为 (二进制内容, mime) 序列，统一转 Base64 data URL。"""
    if not is_vision_enabled():
        return None
    content: list[dict] = [{"type": "text", "text": prompt}]
    for raw, mime in images:
        if not raw:
            continue
        encoded = base64.b64encode(raw).decode("ascii")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime or 'image/png'};base64,{encoded}"},
            }
        )
    if len(content) == 1:
        return None
    messages = [
        {
            "role": "system",
            "content": system_prompt
            or "你是严谨的财务票据 OCR 与结构化信息提取引擎，只输出 JSON。",
        },
        {"role": "user", "content": content},
    ]
    return _post(
        messages,
        api_key=settings.vision_api_key,
        base_url=settings.vision_base_url,
        model=model or settings.ai_vision_model,
        temperature=0.1,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def extract_json(text: str | None) -> Any | None:
    """从模型输出中稳健地提取 JSON（兼容 ```json 代码块与前后说明文字）。"""
    if not text:
        return None
    fenced = _JSON_FENCE.search(text)
    candidate = (fenced.group(1) if fenced else text).strip()
    try:
        return json.loads(candidate)
    except (TypeError, ValueError):
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = candidate.find(opener)
        end = candidate.rfind(closer)
        if start == -1 or end <= start:
            continue
        try:
            return json.loads(candidate[start : end + 1])
        except (TypeError, ValueError):
            continue
    return None


def chat_json(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: float | None = None,
) -> Any | None:
    """要求模型输出 JSON 并解析；失败返回 None。"""
    text = chat_completion(
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    return extract_json(text)
