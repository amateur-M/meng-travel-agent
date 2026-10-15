"""Tests for P3.1 API key authentication (verify_api_key dependency)."""

import pytest
from fastapi import HTTPException

from deps import verify_api_key


class TestVerifyApiKey:
    """verify_api_key bypasses when AUTH_ENABLED=false, enforces when true."""

    @pytest.mark.asyncio
    async def test_bypass_when_auth_disabled(self, monkeypatch):
        monkeypatch.setattr("config.settings.settings.auth_enabled", False)
        # No exception regardless of header presence
        assert await verify_api_key(x_api_key=None) is None
        assert await verify_api_key(x_api_key="anything") is None

    @pytest.mark.asyncio
    async def test_reject_missing_key_when_enabled(self, monkeypatch):
        monkeypatch.setattr("config.settings.settings.auth_enabled", True)
        monkeypatch.setattr("config.settings.settings.api_keys", ["valid-key"])
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(x_api_key=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_reject_invalid_key_when_enabled(self, monkeypatch):
        monkeypatch.setattr("config.settings.settings.auth_enabled", True)
        monkeypatch.setattr("config.settings.settings.api_keys", ["valid-key"])
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(x_api_key="wrong-key")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_accept_valid_key_when_enabled(self, monkeypatch):
        monkeypatch.setattr("config.settings.settings.auth_enabled", True)
        monkeypatch.setattr("config.settings.settings.api_keys", ["valid-key", "another"])
        assert await verify_api_key(x_api_key="valid-key") is None
        assert await verify_api_key(x_api_key="another") is None

    @pytest.mark.asyncio
    async def test_empty_whitelist_rejects_when_enabled(self, monkeypatch):
        monkeypatch.setattr("config.settings.settings.auth_enabled", True)
        monkeypatch.setattr("config.settings.settings.api_keys", [])
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(x_api_key="any-key")
        assert exc_info.value.status_code == 401
