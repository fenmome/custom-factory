"""应用配置（pydantic-settings）。

约定：敏感信息一律从环境变量读取，禁止写入代码或 Git。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


def _first_existing_env_file() -> tuple[Path, ...]:
    return (
        PROJECT_ROOT / ".env",
        BACKEND_ROOT / ".env",
    )


class Settings(BaseSettings):
    """全局配置。"""

    model_config = SettingsConfigDict(
        env_file=_first_existing_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    DEBUG: bool = False

    # 数据库
    DATABASE_URL: str = "mysql+pymysql://cf_user:cf_dev_password@127.0.0.1:3306/custom_factory?charset=utf8mb4"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # 缓存
    REDIS_URL: str = "redis://localhost:6379/0"

    # 安全
    SECRET_KEY: str = "dev-only-secret-key-please-change-in-production-0000"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 8
    RUNNER_TOKEN: str = "dev-only-runner-token-please-change-me-00000000"

    # 存储（必须在项目根目录内）
    STORAGE_ROOT: str = "./data/images"
    PLAN_STORE_ROOT: str = "./data/plans"
    STORAGE_PROFILE: str = "LOCAL_PRIMARY"

    # CORS
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    CORS_ALLOW_CREDENTIALS: bool = True

    # 图片生成（可选）
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    OPENAI_MODEL: str = "gpt-image-1"

    # OCR
    OCR_ENABLED: bool = False
    OCR_RUNTIME_ROOT: str = "./runtime/ocr"

    # 标题池
    TITLE_POOL_VERSION: str = "1.3.0"

    # 业务默认值（非硬编码规则，仅作为兜底引用键）
    DEFAULT_PRODUCT_TYPE_CODE: str = "UV_DTF"
    DEFAULT_USAGE_CODE: str = "small_business_packaging"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                return [item.strip() for item in value.split(",") if item.strip()]
        return value  # type: ignore[return-value]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def storage_root_path(self) -> Path:
        """存储根目录绝对路径（强制限制在项目根目录内）。"""
        candidate = Path(self.STORAGE_ROOT)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        resolved = candidate.resolve()
        project = PROJECT_ROOT.resolve()
        if project not in resolved.parents and resolved != project:
            raise ValueError(f"STORAGE_ROOT 必须位于项目根目录内: {resolved}")
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    @property
    def plan_store_root_path(self) -> Path:
        candidate = Path(self.PLAN_STORE_ROOT)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        resolved = candidate.resolve()
        project = PROJECT_ROOT.resolve()
        if project not in resolved.parents and resolved != project:
            raise ValueError(f"PLAN_STORE_ROOT 必须位于项目根目录内: {resolved}")
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
