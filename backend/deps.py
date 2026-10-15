"""FastAPI dependencies for cross-cutting concerns (P3.1)."""

from typing import Optional

from fastapi import Header, HTTPException, status

from config.settings import settings


async def verify_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    """Validate the X-API-Key header against the configured whitelist.

    Bypassed entirely when AUTH_ENABLED is false (the default for dev/test),
    so existing tests and local development remain unaffected. When enabled,
    requests must carry a key present in the API_KEYS whitelist or they are
    rejected with 401.
    """
    if not settings.auth_enabled:
        return
    if x_api_key and x_api_key in settings.api_keys:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid API key",
        headers={"WWW-Authenticate": "ApiKey"},
    )
