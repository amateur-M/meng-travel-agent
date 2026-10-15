"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _env_list(name: str) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    """Centralized app settings."""

    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # DeepSeek
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    # Qwen (Tongyi Qianwen)
    qwen_api_key: str = os.getenv("QWEN_API_KEY", "")
    qwen_model: str = os.getenv("QWEN_MODEL", "qwen-plus")
    qwen_base_url: str = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    # Kimi (Moonshot)
    kimi_api_key: str = os.getenv("KIMI_API_KEY", "")
    kimi_model: str = os.getenv("KIMI_MODEL", "moonshot-v1-8k")
    kimi_base_url: str = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")

    # Default LLM provider: "openai" | "deepseek" | "qwen" | "kimi"
    default_llm_provider: str = os.getenv("DEFAULT_LLM_PROVIDER", "openai")

    # Weather (QWeather JWT / 和风天气, fallback OpenWeatherMap)
    weather_api_key: str = os.getenv("WEATHER_API_KEY", "")
    weather_provider: str = os.getenv("WEATHER_PROVIDER", "qweather")
    qweather_base_url: str = os.getenv("QWEATHER_BASE_URL", "https://devapi.qweather.com")
    qweather_auth_mode: str = os.getenv("QWEATHER_AUTH_MODE", "auto")
    qweather_credential_id: str = os.getenv("QWEATHER_CREDENTIAL_ID", "")
    qweather_project_id: str = os.getenv("QWEATHER_PROJECT_ID", "")
    qweather_private_key: str = os.getenv("QWEATHER_PRIVATE_KEY", "")
    qweather_private_key_path: str = os.getenv("QWEATHER_PRIVATE_KEY_PATH", "")
    qweather_jwt_ttl_seconds: int = _env_int("QWEATHER_JWT_TTL_SECONDS", 900)

    # Maps
    maps_api_key: str = os.getenv("MAPS_API_KEY", "")
    maps_provider: str = os.getenv("MAPS_PROVIDER", "amap")

    # PostgreSQL (P0.1 行程持久化)
    pg_dsn: str = os.getenv(
        "PG_DSN",
        "postgresql://coupletrip:coupletrip_dev@localhost:5432/coupletrip",
    )

    # Redis (P1.1 对话会话存储)
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # P3.1 鉴权：AUTH_ENABLED=false（默认）时跳过鉴权，保证开发/测试零回归；
    # 生产环境设 true，客户端须在 X-API-Key 头携带 API_KEYS 白名单内的 key。
    auth_enabled: bool = _env_bool("AUTH_ENABLED", False)
    api_keys: list[str] = _env_list("API_KEYS")

    # P3.1 限流：中间件始终挂载，但 RATE_LIMIT_ENABLED=false（默认）时不实际
    # 计数，避免测试高频打端点触发 429；生产环境设 true 开启。
    rate_limit_enabled: bool = _env_bool("RATE_LIMIT_ENABLED", False)
    rate_limit_plan: str = os.getenv("RATE_LIMIT_PLAN", "10/minute")
    rate_limit_chat: str = os.getenv("RATE_LIMIT_CHAT", "30/minute")


settings = Settings()
