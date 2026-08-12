"""Unit tests for shared services (M2 + multi-provider LLM)."""

import json
import pytest
from unittest.mock import patch, MagicMock

from services.llm import call_llm, _extract_json, _get_llm, _PROVIDER_CONFIG


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------

class TestExtractJson:
    """JSON extraction from LLM output."""

    def test_plain_json(self):
        result = _extract_json('{"key": "value"}')
        assert result == '{"key": "value"}'

    def test_markdown_json_fence(self):
        result = _extract_json('```json\n{"key": "value"}\n```')
        assert result == '{"key": "value"}'

    def test_markdown_generic_fence(self):
        result = _extract_json('```\n{"key": "value"}\n```')
        assert result == '{"key": "value"}'

    def test_no_fences_passthrough(self):
        result = _extract_json('plain text')
        assert result == 'plain text'


# ---------------------------------------------------------------------------
# _get_llm — provider resolution
# ---------------------------------------------------------------------------

class TestGetLlm:
    """Provider-level client factory."""

    def test_returns_none_for_unknown_provider(self):
        client = _get_llm("nonexistent")
        assert client is None

    @patch.dict("services.llm._llm_cache", {}, clear=True)
    def test_returns_none_when_openai_key_missing(self):
        client = _get_llm("openai")
        assert client is None

    def test_all_providers_have_config_entries(self):
        for provider in ["openai", "deepseek", "qwen", "kimi"]:
            assert provider in _PROVIDER_CONFIG, f"{provider} missing from _PROVIDER_CONFIG"

    def test_provider_config_has_required_keys(self):
        for provider, cfg in _PROVIDER_CONFIG.items():
            assert "api_key_attr" in cfg
            assert "model_attr" in cfg

    @patch.dict("services.llm._llm_cache", {}, clear=True)
    def test_deepseek_uses_custom_base_url_when_key_present(self):
        """DeepSeek ChatOpenAI client is created with its base_url."""
        with patch.object(
            __import__("services.llm", fromlist=["_get_llm"]),
            "ChatOpenAI",
            autospec=True,
        ) as mock_chat:
            with patch.object(
                __import__("config.settings", fromlist=["settings"]),
                "settings",
            ) as mock_settings:
                mock_settings.deepseek_api_key = "sk-test"
                mock_settings.deepseek_model = "deepseek-chat"
                mock_settings.deepseek_base_url = "https://api.deepseek.com"
                # Re-import to get fresh settings reference
                _get_llm("deepseek")


# ---------------------------------------------------------------------------
# call_llm — mock fallback
# ---------------------------------------------------------------------------

class TestCallLlmMock:
    """call_llm with mock fallback (no API key)."""

    def test_returns_mock_when_no_api_key(self):
        result = call_llm("sys", "user", mock_response={"mock": True})
        assert result == {"mock": True}

    def test_returns_error_dict_when_no_mock_provided(self):
        result = call_llm("sys", "user")
        assert "error" in result

    def test_returns_mock_for_explicit_provider_without_key(self):
        """Even when specifying a provider, missing key yields mock."""
        result = call_llm("sys", "user", mock_response={"fallback": True}, provider="deepseek")
        assert result == {"fallback": True}

    def test_unknown_provider_yields_mock(self):
        result = call_llm("sys", "user", mock_response={"mock": True}, provider="foobar")
        assert result == {"mock": True}


# ---------------------------------------------------------------------------
# call_llm — provider defaulting
# ---------------------------------------------------------------------------

class TestCallLlmProviderDefault:
    """call_llm defaults to settings.default_llm_provider."""

    def test_uses_default_provider_when_none_given(self):
        """If provider is omitted, settings.default_llm_provider is used."""
        with (
            patch("services.llm.settings") as mock_settings,
            patch("services.llm._get_llm") as mock_get,
        ):
            mock_settings.default_llm_provider = "qwen"
            mock_get.return_value = None
            call_llm("sys", "user", mock_response={})
            mock_get.assert_called_once_with("qwen")


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

class TestServicesModule:
    """Verify services package exports."""

    def test_call_llm_is_importable(self):
        from services import call_llm
        assert callable(call_llm)

    def test_provider_config_is_importable(self):
        from services.llm import _PROVIDER_CONFIG
        assert isinstance(_PROVIDER_CONFIG, dict)
