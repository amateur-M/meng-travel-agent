"""OFFLINE_MODE: deterministic, offline runs for smoke tests, demos and CI.

Why a dedicated switch instead of blanking the key env vars: an environment
variable must be **non-empty** to override a value in ``.env``. Setting
``$env:OPENAI_API_KEY=''`` does *not* clear it — pydantic-settings treats an
empty environment variable as unset — so the app kept using the real keys and
the smoke test silently made real (billable) LLM/weather/map requests.

Settings are constructed with explicit init arguments here, which have the
highest priority in pydantic-settings, so these tests are hermetic: they do not
depend on whatever ``.env`` or the ambient environment happens to contain.
"""

from config.settings import Settings

CREDENTIAL_FIELDS = (
    "openai_api_key",
    "deepseek_api_key",
    "qwen_api_key",
    "kimi_api_key",
    "weather_api_key",
    "maps_api_key",
)


def test_offline_mode_clears_every_external_credential():
    settings = Settings(
        offline_mode=True,
        openai_api_key="sk-openai",
        deepseek_api_key="sk-deepseek",
        qwen_api_key="sk-qwen",
        kimi_api_key="sk-kimi",
        weather_api_key="weather-key",
        maps_api_key="maps-key",
    )
    for field in CREDENTIAL_FIELDS:
        assert getattr(settings, field) == "", f"{field} survived offline mode"


def test_offline_mode_keeps_non_credential_configuration():
    """Offline mode is about credentials, not about the whole configuration."""
    settings = Settings(
        offline_mode=True,
        default_llm_provider="qwen",
        json_logs=False,
        rate_limit_plan="7/minute",
    )
    assert settings.default_llm_provider == "qwen"
    assert settings.json_logs is False
    assert settings.rate_limit_plan == "7/minute"


def test_credentials_are_kept_when_not_offline():
    settings = Settings(offline_mode=False, openai_api_key="sk-openai")
    assert settings.openai_api_key == "sk-openai"


def test_offline_mode_defaults_to_off():
    """A live deployment must never end up silently mocked."""
    assert Settings(openai_api_key="sk-x").offline_mode is False
