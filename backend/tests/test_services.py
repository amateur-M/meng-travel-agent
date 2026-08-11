"""Unit tests for shared services (M2)."""

import json
import pytest
from unittest.mock import patch, MagicMock

from services.llm import call_llm, _extract_json


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


class TestCallLlmMock:
    """call_llm with mock fallback (no API key)."""

    def test_returns_mock_when_no_api_key(self):
        result = call_llm("sys", "user", mock_response={"mock": True})
        assert result == {"mock": True}

    def test_returns_error_dict_when_no_mock_provided(self):
        result = call_llm("sys", "user")
        assert "error" in result


class TestServicesModule:
    """Verify services package exports."""

    def test_call_llm_is_importable(self):
        from services import call_llm
        assert callable(call_llm)
