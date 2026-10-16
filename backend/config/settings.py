"""Application configuration via pydantic-settings (P3.3).

Replaces the hand-rolled os.getenv Settings with BaseSettings for
type-safe env binding, validation, and .env file layering. The module
still exports a `settings` singleton so all `from config.settings
import settings` call sites — and conftest monkeypatch paths — remain
unchanged.
"""

import json
from typing import Annotated, List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _split_csv(value: str | List[str]) -> List[str]:
    """Accept both JSON arrays and comma-separated strings for env compat."""
    if isinstance(value, list):
        return value
    if not value or not value.strip():
        return []
    stripped = value.strip()
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
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

    # 对话会话存储已迁至 PostgreSQL（V3/P1），Redis 依赖随之移除。
    # 若将来以多 worker 部署，需要为 SSE 事件扇出与共享限流计数重新引入
    # broker —— 届时它是为流式与限流服务的，与聊天记忆无关。

    # P3.1 鉴权
    auth_enabled: bool = False
    # NoDecode: 跳过 pydantic-settings 对 List 字段的 JSON 预解码，交给 _split_csv 处理逗号分隔/JSON 数组
    api_keys: Annotated[List[str], NoDecode] = []

    # P3.1 限流
    rate_limit_enabled: bool = False
    rate_limit_plan: str = "10/minute"
    rate_limit_chat: str = "30/minute"

    # P3.2 可观测性
    json_logs: bool = True

    # P3.3 CORS origins（逗号分隔）；默认开发环境，生产从 env 注入
    cors_origins: Annotated[List[str], NoDecode] = ["http://localhost:5173"]

    # 离线/确定性模式：给冒烟测试、演示与 CI 用。
    # 置 true 时清空全部外部凭据，于是 LLM 与天气/地图工具各自走既有的 mock 路径
    # —— 既不发真实请求、不花钱，也不受上游输出波动影响（真实模型的槽位提取结果
    # 会随版本变化，断言会因此变得不稳定）。
    #
    # 为什么需要一个专门的开关：环境变量必须给**非空**值才能覆盖 .env。
    # 把某把 key 设成空字符串并不会覆盖 .env 里的值（pydantic-settings 视空环境
    # 变量为未设置），所以 `$env:OPENAI_API_KEY=''` 这种直觉做法是无效的 ——
    # 曾因此在冒烟测试里意外发出了真实的 LLM/天气/地图请求。
    offline_mode: bool = False

    # Allow comma-separated strings from env for list fields
    @field_validator("api_keys", mode="before")
    @classmethod
    def _parse_api_keys(cls, v):
        return _split_csv(v)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v):
        return _split_csv(v)

    @model_validator(mode="after")
    def _clear_credentials_when_offline(self):
        """In offline mode, drop every external credential.

        Clearing them (rather than adding checks in each caller) means every
        existing mock fallback engages through the path it already has.
        """
        if self.offline_mode:
            for name in (
                "openai_api_key",
                "deepseek_api_key",
                "qwen_api_key",
                "kimi_api_key",
                "weather_api_key",
                "maps_api_key",
            ):
                if hasattr(self, name):
                    setattr(self, name, "")
        return self


settings = Settings()
