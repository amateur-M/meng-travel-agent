"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


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

    # Maps
    maps_api_key: str = os.getenv("MAPS_API_KEY", "")
    maps_provider: str = os.getenv("MAPS_PROVIDER", "amap")


settings = Settings()
