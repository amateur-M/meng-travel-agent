"""QWeather authentication helpers.

QWeather supports signed Ed25519 JWTs and API Keys. This module keeps the
credentials in one place and builds the correct request headers for both
GeoAPI v2 and Weather API v1.
"""

import base64
import json
import time
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class QWeatherAuthError(ValueError):
    """Raised when QWeather credentials are missing or malformed."""


def _b64url_encode(data: bytes) -> str:
    """Encode bytes using JWT-compatible base64url without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _looks_like_pem(value: str) -> bool:
    return "-----BEGIN" in value and "PRIVATE KEY-----" in value


def _looks_like_jwt(value: str) -> bool:
    parts = value.split(".")
    return len(parts) == 3 and all(part for part in parts)


def _load_private_key(value: str) -> Ed25519PrivateKey:
    try:
        key = serialization.load_pem_private_key(
            value.encode("utf-8"),
            password=None,
        )
    except Exception as exc:
        raise QWeatherAuthError(
            "Unable to parse QWeather Ed25519 private key"
        ) from exc

    if not isinstance(key, Ed25519PrivateKey):
        raise QWeatherAuthError(
            "QWeather JWT authentication requires an Ed25519 private key"
        )
    return key


def _generate_jwt(
    private_key: Ed25519PrivateKey,
    credential_id: str,
    project_id: str,
    ttl_seconds: int = 900,
) -> str:
    """Build a QWeather-compatible signed JWT from an Ed25519 private key."""
    now = int(time.time())
    iat = now - 30
    ttl = min(max(int(ttl_seconds or 900), 60), 86400)
    exp = now + ttl

    header = {"alg": "EdDSA", "kid": credential_id}
    payload = {"sub": project_id, "iat": iat, "exp": exp}

    signing_input = ".".join(
        [
            _b64url_encode(
                json.dumps(header, separators=(",", ":")).encode("utf-8")
            ),
            _b64url_encode(
                json.dumps(payload, separators=(",", ":")).encode("utf-8")
            ),
        ]
    )
    signature = private_key.sign(signing_input.encode("ascii"))
    return f"{signing_input}.{_b64url_encode(signature)}"


def _resolve_private_key(settings: Any) -> Ed25519PrivateKey | None:
    """Resolve the Ed25519 private key from the available settings."""
    private_key_text = getattr(settings, "qweather_private_key", "") or ""
    if _looks_like_pem(private_key_text):
        return _load_private_key(private_key_text)

    weather_key = getattr(settings, "weather_api_key", "") or ""
    if _looks_like_pem(weather_key):
        return _load_private_key(weather_key)

    key_path = getattr(settings, "qweather_private_key_path", "") or ""
    if key_path:
        path = Path(key_path)
        if not path.is_file():
            raise QWeatherAuthError(
                f"QWEATHER_PRIVATE_KEY_PATH does not exist: {path}"
            )
        try:
            return _load_private_key(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise QWeatherAuthError(
                f"Unable to read QWEATHER_PRIVATE_KEY_PATH: {path}"
            ) from exc

    return None


def build_qweather_headers(settings: Any) -> dict[str, str]:
    """Return QWeather request headers for the configured credential type.

    `WEATHER_API_KEY` can contain one of:
    - an Ed25519 PEM private key (a JWT is generated and cached per call)
    - an already signed JWT (used as-is)
    - a plain API key (sent as `X-QW-Api-Key`)

    The explicit `QWEATHER_AUTH_MODE` can be `auto`, `jwt`, or `api_key`.
    """
    token = (getattr(settings, "weather_api_key", "") or "").strip()
    mode = (getattr(settings, "qweather_auth_mode", "") or "auto").lower()

    if mode == "api_key":
        if not token:
            raise QWeatherAuthError(
                "QWEATHER_AUTH_MODE=api_key requires WEATHER_API_KEY"
            )
        return {"X-QW-Api-Key": token}

    if mode == "jwt":
        if _looks_like_jwt(token):
            return {"Authorization": f"Bearer {token}"}
        private_key = _resolve_private_key(settings)
        if private_key is None:
            raise QWeatherAuthError(
                "QWEATHER_AUTH_MODE=jwt requires an Ed25519 private key "
                "or a signed JWT in WEATHER_API_KEY"
            )
        credential_id = (getattr(settings, "qweather_credential_id", "") or "").strip()
        project_id = (getattr(settings, "qweather_project_id", "") or "").strip()
        if not credential_id or not project_id:
            raise QWeatherAuthError(
                "QWEATHER_CREDENTIAL_ID and QWEATHER_PROJECT_ID are required "
                "to generate a QWeather JWT"
            )
        ttl = int(getattr(settings, "qweather_jwt_ttl_seconds", 900) or 900)
        jwt_token = _generate_jwt(
            private_key,
            credential_id=credential_id,
            project_id=project_id,
            ttl_seconds=ttl,
        )
        return {"Authorization": f"Bearer {jwt_token}"}

    # auto mode
    if _looks_like_pem(token):
        private_key = _load_private_key(token)
        credential_id = (getattr(settings, "qweather_credential_id", "") or "").strip()
        project_id = (getattr(settings, "qweather_project_id", "") or "").strip()
        if not credential_id or not project_id:
            raise QWeatherAuthError(
                "QWEATHER_CREDENTIAL_ID and QWEATHER_PROJECT_ID are required "
                "to generate a QWeather JWT"
            )
        ttl = int(getattr(settings, "qweather_jwt_ttl_seconds", 900) or 900)
        jwt_token = _generate_jwt(
            private_key,
            credential_id=credential_id,
            project_id=project_id,
            ttl_seconds=ttl,
        )
        return {"Authorization": f"Bearer {jwt_token}"}

    if _looks_like_jwt(token):
        return {"Authorization": f"Bearer {token}"}

    if token:
        return {"X-QW-Api-Key": token}

    raise QWeatherAuthError(
        "WEATHER_API_KEY is not configured for QWeather"
    )
