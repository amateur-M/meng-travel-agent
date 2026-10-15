"""Application configuration via pydantic-settings (P3.3).

Replaces the hand-rolled os.getenv Settings with BaseSettings for
type-safe env binding, validation, and .env file layering. The module
still exports a `settings` singleton so all `from config.settings
import settings` call sites — and conftest monkeypatch paths — remain
unchanged.
"""

from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: str | List[str]) -> List[str]:
    """Accept both JSON lists and comma-separated strings for env compat."""
    if isinstance(value, list):
        return value
    if not value or not value.strip():
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """Centralized app settings, bound from environment / .env files."""

    model_config = SettingsConfigDict(
        env_file=(".env.dev", ".env", ".env.prod"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"

    # Qwen (Tongyi Qianwen)
    qwen_api_key: str = ""
    qwen_model: str = "qwen-plus"
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Kimi (Moonshot)
    kimi_api_key: str = ""
    kimi_model: str = "moonshot-v1-8k"
    kimi_base_url: str = "https://api.moonshot.cn/v1"

    # Default LLM provider: "openai" | "deepseek" | "qwen" | "kimi"
    default_llm_provider: str = "openai"

    # Weather (QWeather JWT / 和风天气, fallback OpenWeatherMap)
    weather_api_key: str = ""
    weather_provider: str = "qweather"
    qweather_base_url: str = "https://devapi.qweather.com"
    qweather_auth_mode: str = "auto"
    qweather_credential_id: str = ""
    qweather_project_id: str = ""
    qweather_private_key: str = ""
    qweather_private_key_path: str = ""
    qweather_jwt_ttl_seconds: int = 900

    # Maps
    maps_api_key: str = ""
    maps_provider: str = "amap"

    # PostgreSQL (P0.1 行程持久化)
    pg_dsn: str = "postgresql://coupletrip:coupletrip_dev@localhost:5432/coupletrip"

    # Redis (P1.1 对话会话存储)
    redis_url: str = "redis://localhost:6379/0"

    # P3.1 鉴权
    auth_enabled: bool = False
    api_keys: List[str] = []

    # P3.1 限流
    rate_limit_enabled: bool = False
    rate_limit_plan: str = "10/minute"
    rate_limit_chat: str = "30/minute"

    # P3.2 可观测性
    json_logs: bool = True

    # P3.3 CORS origins（逗号分隔）；默认开发环境，生产从 env 注入
    cors_origins: List[str] = ["http://localhost:5173"]

    # Allow comma-separated strings from env for list fields
    @field_validator("api_keys", mode="before")
    @classmethod
    def _parse_api_keys(cls, v):
        return _split_csv(v)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v):
        return _split_csv(v)


settings = Settings()
