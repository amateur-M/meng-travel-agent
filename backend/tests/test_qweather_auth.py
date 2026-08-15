"""Tests for QWeather JWT and API Key authentication."""

import base64
import json
import time
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from services.qweather_auth import (
    QWeatherAuthError,
    build_qweather_headers,
)


def _private_key():
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    return key, pem


def _decode_jwt_part(part: str) -> dict:
    padding = "=" * (-len(part) % 4)
    raw = base64.urlsafe_b64decode(part + padding)
    return json.loads(raw)


def _settings(**overrides):
    values = {
        "weather_api_key": "",
        "qweather_auth_mode": "auto",
        "qweather_credential_id": "credential-123",
        "qweather_project_id": "project-456",
        "qweather_private_key": "",
        "qweather_private_key_path": "",
        "qweather_jwt_ttl_seconds": 900,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_auto_pem_private_key_generates_bearer_jwt():
    private_key, pem = _private_key()
    headers = build_qweather_headers(
        _settings(weather_api_key=pem)
    )

    token = headers["Authorization"]
    assert token.startswith("Bearer ")

    jwt_token = token.split(" ", 1)[1]
    header_part, payload_part, signature_part = jwt_token.split(".")
    header = _decode_jwt_part(header_part)
    payload = _decode_jwt_part(payload_part)

    assert header == {"alg": "EdDSA", "kid": "credential-123"}
    assert payload["sub"] == "project-456"
    assert payload["iat"] <= int(time.time())
    assert payload["exp"] > int(time.time())

    signature = base64.urlsafe_b64decode(
        signature_part + "=" * (-len(signature_part) % 4)
    )
    private_key.public_key().verify(
        signature,
        f"{header_part}.{payload_part}".encode("ascii"),
    )


def test_auto_signed_jwt_is_used_as_is():
    token = "header.payload.signature"
    assert build_qweather_headers(
        _settings(weather_api_key=token)
    ) == {"Authorization": f"Bearer {token}"}


def test_auto_short_value_is_api_key():
    assert build_qweather_headers(
        _settings(weather_api_key="ABCD1234EFGH")
    ) == {"X-QW-Api-Key": "ABCD1234EFGH"}


def test_explicit_api_key_mode_uses_api_key_header():
    assert build_qweather_headers(
        _settings(
            weather_api_key="ABCD1234EFGH",
            qweather_auth_mode="api_key",
        )
    ) == {"X-QW-Api-Key": "ABCD1234EFGH"}


def test_explicit_jwt_mode_can_use_pem_private_key():
    _, pem = _private_key()
    headers = build_qweather_headers(
        _settings(
            weather_api_key=pem,
            qweather_auth_mode="jwt",
        )
    )
    assert headers["Authorization"].startswith("Bearer ")


def test_missing_credential_id_raises_clear_error():
    _, pem = _private_key()
    with pytest.raises(QWeatherAuthError, match="QWEATHER_CREDENTIAL_ID"):
        build_qweather_headers(
            _settings(
                weather_api_key=pem,
                qweather_credential_id="",
            )
        )


def test_missing_project_id_raises_clear_error():
    _, pem = _private_key()
    with pytest.raises(QWeatherAuthError, match="QWEATHER_PROJECT_ID"):
        build_qweather_headers(
            _settings(
                weather_api_key=pem,
                qweather_project_id="",
            )
        )


def test_empty_credentials_raise_clear_error():
    with pytest.raises(QWeatherAuthError, match="not configured"):
        build_qweather_headers(_settings())
