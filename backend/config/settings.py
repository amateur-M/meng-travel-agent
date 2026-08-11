"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Centralized app settings."""

    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Weather
    weather_api_key: str = os.getenv("WEATHER_API_KEY", "")
    weather_provider: str = os.getenv("WEATHER_PROVIDER", "openweathermap")

    # Maps
    maps_api_key: str = os.getenv("MAPS_API_KEY", "")
    maps_provider: str = os.getenv("MAPS_PROVIDER", "amap")


settings = Settings()
