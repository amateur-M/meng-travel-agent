"""SessionStore — Redis-backed conversation session storage (P1.1).

Stores chat slots and history per session_id with a 30-minute TTL.
Uses redis.asyncio for non-blocking I/O.

When Redis is unreachable, degrades gracefully: all operations return
safe fallbacks (empty slots, False) instead of raising — the chat
endpoint can still function without persistence (session is lost on
refresh, but the API doesn't 500).
"""

import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from config.settings import settings

logger = logging.getLogger("coupletrip")

# ── Redis client (lazy singleton) ────────────────────────────────────

_redis: Optional[aioredis.Redis] = None
_redis_unavailable = False
_redis_error: Optional[str] = None

SESSION_TTL = 1800  # 30 minutes
_SLOT_FIELDS = ("destination", "start_date", "end_date", "budget", "origin", "preferences", "pace")


async def _get_redis() -> Optional[aioredis.Redis]:
    """Return the shared async Redis client, initialising on first call.

    The failure reason is kept in ``_redis_error`` so ``health()`` can report
    it (T0.4) instead of the degradation living only in a warning log.
    """
    global _redis, _redis_unavailable, _redis_error
    if _redis is not None:
        return _redis
    if _redis_unavailable:
        return None

    try:
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        _redis = client
        _redis_error = None
        logger.info("SessionStore: Redis connected")
        return client
    except Exception as exc:
        _redis_error = f"{type(exc).__name__}: {exc}"
        logger.warning("SessionStore: Redis unavailable — sessions will not persist: %s", exc)
        _redis_unavailable = True
        return None


def _session_key(session_id: str) -> str:
    return f"chat:{session_id}"


def _history_key(session_id: str) -> str:
    return f"chat:{session_id}:history"


# ── SessionStore ─────────────────────────────────────────────────────

class SessionStore:
    """Manages chat session slots + history in Redis with TTL."""

    async def get_slots(self, session_id: str) -> dict:
        """Return the current slot values for a session (empty dict if new/failed)."""
        r = await _get_redis()
        if r is None:
            return {}
        try:
            raw = await r.hgetall(_session_key(session_id))
            return {k: v for k, v in raw.items() if k in _SLOT_FIELDS} if raw else {}
        except Exception as exc:
            logger.warning("SessionStore.get_slots failed: %s", exc)
            return {}

    async def merge_slots(self, session_id: str, new_slots: dict) -> dict:
        """Atomically merge new_slots into existing slots, refresh TTL.

        Returns the full merged slot dict.
        """
        r = await _get_redis()
        if r is None:
            return new_slots
        try:
            key = _session_key(session_id)
            # Only store non-empty values
            to_set = {k: str(v) for k, v in new_slots.items() if v}
            if to_set:
                await r.hset(key, mapping=to_set)
            await r.expire(key, SESSION_TTL)
            raw = await r.hgetall(key)
            return {k: v for k, v in raw.items() if k in _SLOT_FIELDS} if raw else {}
        except Exception as exc:
            logger.warning("SessionStore.merge_slots failed: %s", exc)
            return new_slots

    async def get_history(self, session_id: str) -> list[dict]:
        """Return the message history for a session."""
        r = await _get_redis()
        if r is None:
            return []
        try:
            raw = await r.lrange(_history_key(session_id), 0, -1)
            return [json.loads(item) for item in raw]
        except Exception as exc:
            logger.warning("SessionStore.get_history failed: %s", exc)
            return []

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the session history, refresh TTL."""
        r = await _get_redis()
        if r is None:
            return
        try:
            key = _history_key(session_id)
            await r.rpush(key, json.dumps({"role": role, "content": content}, ensure_ascii=False))
            await r.expire(key, SESSION_TTL)
        except Exception as exc:
            logger.warning("SessionStore.add_message failed: %s", exc)

    async def clear(self, session_id: str) -> None:
        """Delete all data for a session."""
        r = await _get_redis()
        if r is None:
            return
        try:
            await r.delete(_session_key(session_id), _history_key(session_id))
        except Exception as exc:
            logger.warning("SessionStore.clear failed: %s", exc)

    # ── T0.4: Storage visibility ──────────────────────────────────

    async def health(self) -> dict:
        """Report Redis connectivity for ``/health``. Never raises."""
        r = await _get_redis()
        if r is None:
            return {
                "configured": bool(settings.redis_url),
                "connected": False,
                "error": _redis_error or "client unavailable",
            }
        try:
            await r.ping()
            return {"configured": True, "connected": True, "error": None}
        except Exception as exc:
            return {
                "configured": True,
                "connected": False,
                "error": f"{type(exc).__name__}: {exc}",
            }


# ── Module-level singleton ───────────────────────────────────────────

session_store = SessionStore()
