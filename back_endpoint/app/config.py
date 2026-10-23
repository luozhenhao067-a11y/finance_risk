"""全局配置：环境变量可覆盖默认值。

AI 相关配置统一从 `back_endpoint/.env` 读取（也可使用进程环境变量覆盖）。
未配置 `AI_API_KEY` 时，所有 AI 能力自动降级为 Mock / 规则兜底。
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.engine import URL

BASE_DIR = Path(__file__).resolve().parent.parent  # back_endpoint/

try:  # python-dotenv 为可选依赖：缺失时仍可用系统环境变量启动
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # pragma: no cover - 仅在未安装 python-dotenv 时触发
    pass


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    db_user: str = os.getenv("DB_USER", "root")
    db_password: str = os.getenv("DB_PASSWORD", "Root@123456")
    db_host: str = os.getenv("DB_HOST", "127.0.0.1")
    db_port: int = int(os.getenv("DB_PORT", "3306"))
    db_name: str = os.getenv("DB_NAME", "financial_risk_audit")

    jwt_secret: str = os.getenv("JWT_SECRET", "finance-risk-audit-dev-secret-change-me")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = _env_int("JWT_EXPIRE_MINUTES", 120)

    storage_dir: Path = field(default_factory=lambda: Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "storage"))))
    files_subdir: str = "files"
    exports_subdir: str = "exports"

    max_upload_bytes: int = 20 * 1024 * 1024
    allowed_extensions: tuple = ("pdf", "png", "jpg", "jpeg")

    login_max_fails: int = 5
    login_lock_minutes: int = 15

    # ---------- 大模型（OpenAI 兼容 /chat/completions） ----------
    ai_api_key: str = os.getenv("AI_API_KEY", "").strip()
    ai_base_url: str = os.getenv("AI_BASE_URL", "https://api.deepseek.com/v1").strip()
    ai_model: str = os.getenv("AI_MODEL", "deepseek-chat").strip()
    # 多模态模型留空表示不启用 Vision，附件解析直接走 Mock
    ai_vision_model: str = os.getenv("AI_VISION_MODEL", "").strip()
    ai_vision_api_key: str = os.getenv("AI_VISION_API_KEY", "").strip()
    ai_vision_base_url: str = os.getenv("AI_VISION_BASE_URL", "").strip()
    ai_timeout_seconds: float = _env_float("AI_TIMEOUT_SECONDS", 30.0)
    ai_max_tokens: int = _env_int("AI_MAX_TOKENS", 1024)
    ai_temperature: float = _env_float("AI_TEMPERATURE", 0.2)
    ai_max_pages: int = _env_int("AI_MAX_PAGES", 2)

    cors_origins: tuple = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    )

    @property
    def db_url(self) -> URL:
        return URL.create(
            drivername="mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        )

    @property
    def files_dir(self) -> Path:
        return self.storage_dir / self.files_subdir

    @property
    def exports_dir(self) -> Path:
        return self.storage_dir / self.exports_subdir

    @property
    def vision_api_key(self) -> str:
        return self.ai_vision_api_key or self.ai_api_key

    @property
    def vision_base_url(self) -> str:
        return self.ai_vision_base_url or self.ai_base_url

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai_api_key and self.ai_model)

    @property
    def ai_vision_enabled(self) -> bool:
        return bool(self.vision_api_key and self.ai_vision_model)


settings = Settings()
