"""ConversationStore — PostgreSQL persistence for chat sessions and messages.

Sessions, their slots and their full transcript live in PostgreSQL — the same
database that already holds trip plans — so a conversation survives page
refreshes, tab closes, backend restarts and days of inactivity. This replaces
the Redis session store (P1.1), whose 30-minute TTL meant "come back tomorrow"
silently started from scratch.

Design notes:
  - **The event loop is never blocked, but the driver is sync.** DB work runs
    in a worker thread via ``asyncio.to_thread``. psycopg's *async* mode would
    be the obvious choice, except it refuses to run on Windows' default
    ``ProactorEventLoop`` (``InterfaceError: Psycopg cannot use the
    'ProactorEventLoop' to run in async mode``) — and Windows is the primary
    dev platform here. Thread offload gives the same guarantee (the V2 P0.2
    lesson was "never block the event loop", not "always use async drivers")
    and behaves identically on Linux.
  - The public surface is ``async`` so callers never think about threads.
  - DDL is idempotent and runs on first use, same as ``PlanStore``.
  - When PostgreSQL is unreachable, reads return empty values and writes return
    ``False`` — but the reason is recorded and surfaced via :meth:`health`, so
    the degradation is never silent (T0.4).
  - :meth:`append_message` is idempotent on ``message_id``, so a client retry
    cannot duplicate a turn (recovery matrix #6).
"""

import asyncio
import json
import logging
import uuid
from typing import Optional

import psycopg
from psycopg_pool import ConnectionPool

from config.settings import settings

logger = logging.getLogger("coupletrip")

# ── Connection pool (lazy singleton) ─────────────────────────────────

_pool: Optional[ConnectionPool] = None
_pool_unavailable = False
_pool_error: Optional[str] = None

_SLOT_FIELDS = (
    "destination",
    "start_date",
    "end_date",
    "budget",
    "origin",
    "preferences",
    "pace",
)


def _diagnose(pool_exc: Exception) -> str:
    """Explain *why* the pool failed, not just that it timed out.

    ``pool.open(wait=True)`` reports a bare ``PoolTimeout``; the actionable
    cause (bad credentials, missing database, wrong host) is only visible from
    a direct connect attempt. Reporting the timeout instead cost real debugging
    time when this was first investigated, so the real error wins.
    """
    try:
        conn = psycopg.connect(settings.pg_dsn, connect_timeout=5)
        conn.close()
    except Exception as root:
        return f"{type(root).__name__}: {root}"
    return f"{type(pool_exc).__name__}: {pool_exc}"


def _get_pool() -> Optional[ConnectionPool]:
    """Return the shared pool, initialising it on first call (blocking).

    A failure is cached so later calls skip instantly instead of re-paying the
    connect timeout, and the reason is kept for :meth:`health`.
    """
    global _pool, _pool_unavailable, _pool_error
    if _pool is not None:
        return _pool
    if _pool_unavailable:
        return None

    pool: Optional[ConnectionPool] = None
    try:
        pool = ConnectionPool(
            conninfo=settings.pg_dsn,
            min_size=1,
            max_size=5,
            open=False,
        )
        # Fail fast rather than hanging requests behind an unreachable database.
        pool.open(wait=True, timeout=5)
        with pool.connection() as conn:
            _init_ddl(conn)
        _pool = pool
        _pool_error = None
        logger.info("ConversationStore: PostgreSQL pool initialised")
        return pool
    except Exception as exc:
        _pool_error = _diagnose(exc)
        logger.warning(
            "ConversationStore: PostgreSQL unavailable — chat history will not persist: %s",
            _pool_error,
        )
        if pool is not None:
            try:
                pool.close()
            except Exception:  # pragma: no cover - best-effort cleanup
                pass
        _pool_unavailable = True
        return None


def _init_ddl(conn) -> None:
    """Create the chat tables if they do not exist (idempotent)."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id   TEXT PRIMARY KEY,
                title        TEXT,
                summary      TEXT,
                slots        JSONB NOT NULL DEFAULT '{}'::jsonb,
                plan_request JSONB,
                last_plan_id TEXT,
                client_id    TEXT,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id         BIGSERIAL PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
                message_id TEXT UNIQUE,
                role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content    TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session
            ON chat_messages (session_id, id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated
            ON chat_sessions (updated_at DESC)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_client
            ON chat_sessions (client_id, updated_at DESC)
        """)
    conn.commit()


def generate_session_id() -> str:
    """Generate a URL-safe session ID."""
    return uuid.uuid4().hex


def _iso(value) -> Optional[str]:
    return value.isoformat() if value else None


# ── ConversationStore ────────────────────────────────────────────────

class ConversationStore:
    """CRUD interface for chat sessions and messages backed by PostgreSQL.

    Public methods are ``async`` and offload to a worker thread; the private
    ``_*`` methods hold the actual (blocking) SQL so the logic stays readable.
    """

    # ── sessions ──────────────────────────────────────────────────

    async def ensure_session(self, session_id: str, client_id: Optional[str] = None) -> bool:
        """Create the session row if it does not exist yet.

        Lets a client-supplied session_id self-heal instead of failing the
        foreign key on the first message.
        """
        return await asyncio.to_thread(self._ensure_session, session_id, client_id)

    def _ensure_session(self, session_id: str, client_id: Optional[str]) -> bool:
        pool = _get_pool()
        if pool is None:
            return False
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO chat_sessions (session_id, client_id)
                        VALUES (%s, %s)
                        ON CONFLICT (session_id) DO NOTHING
                        """,
                        (session_id, client_id),
                    )
                conn.commit()
            return True
        except Exception as exc:
            logger.warning("ConversationStore.ensure_session failed: %s", exc)
            return False

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Return session metadata (without the transcript), or ``None``."""
        return await asyncio.to_thread(self._get_session, session_id)

    def _get_session(self, session_id: str) -> Optional[dict]:
        pool = _get_pool()
        if pool is None:
            return None
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT s.session_id, s.title, s.summary, s.slots,
                               s.plan_request, s.last_plan_id, s.client_id,
                               s.created_at, s.updated_at,
                               COALESCE(c.cnt, 0) AS message_count
                        FROM chat_sessions s
                        LEFT JOIN (
                            SELECT session_id, COUNT(*) AS cnt
                            FROM chat_messages GROUP BY session_id
                        ) c ON c.session_id = s.session_id
                        WHERE s.session_id = %s
                        """,
                        (session_id,),
                    )
                    row = cur.fetchone()
            if row is None:
                return None
            return {
                "session_id": row[0],
                "title": row[1],
                "summary": row[2],
                "slots": row[3] or {},
                "plan_request": row[4],
                "last_plan_id": row[5],
                "client_id": row[6],
                "created_at": _iso(row[7]),
                "updated_at": _iso(row[8]),
                "message_count": int(row[9]),
            }
        except Exception as exc:
            logger.warning("ConversationStore.get_session failed: %s", exc)
            return None

    async def list_sessions(
        self,
        client_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """Return session summaries, most recently active first.

        ``client_id=None`` lists every session (single-user deployments and
        tests); passing one scopes the list to that client.
        """
        return await asyncio.to_thread(self._list_sessions, client_id, limit, offset)

    def _list_sessions(
        self, client_id: Optional[str], limit: int, offset: int
    ) -> list[dict]:
        pool = _get_pool()
        if pool is None:
            return []
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT s.session_id, s.title, s.updated_at, s.last_plan_id,
                               COALESCE(c.cnt, 0) AS message_count,
                               p.content AS preview
                        FROM chat_sessions s
                        LEFT JOIN (
                            SELECT session_id, COUNT(*) AS cnt
                            FROM chat_messages GROUP BY session_id
                        ) c ON c.session_id = s.session_id
                        LEFT JOIN LATERAL (
                            SELECT content FROM chat_messages
                            WHERE session_id = s.session_id
                            ORDER BY id DESC LIMIT 1
                        ) p ON TRUE
                        WHERE (%s::text IS NULL OR s.client_id = %s)
                        ORDER BY s.updated_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (client_id, client_id, limit, offset),
                    )
                    rows = cur.fetchall()
            return [
                {
                    "session_id": row[0],
                    "title": row[1],
                    "updated_at": _iso(row[2]),
                    "last_plan_id": row[3],
                    "message_count": int(row[4]),
                    "preview": (row[5] or "")[:80],
                }
                for row in rows
            ]
        except Exception as exc:
            logger.warning("ConversationStore.list_sessions failed: %s", exc)
            return []

    async def rename_session(self, session_id: str, title: str) -> bool:
        """Set an explicit session title."""
        return await asyncio.to_thread(self._rename_session, session_id, title)

    def _rename_session(self, session_id: str, title: str) -> bool:
        pool = _get_pool()
        if pool is None:
            return False
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE chat_sessions SET title = %s WHERE session_id = %s",
                        (title, session_id),
                    )
                    updated = cur.rowcount
                conn.commit()
            return updated > 0
        except Exception as exc:
            logger.warning("ConversationStore.rename_session failed: %s", exc)
            return False

    async def set_title_if_empty(self, session_id: str, title: str) -> bool:
        """Set the title only while it is still unset (first message wins)."""
        return await asyncio.to_thread(self._set_title_if_empty, session_id, title)

    def _set_title_if_empty(self, session_id: str, title: str) -> bool:
        pool = _get_pool()
        if pool is None:
            return False
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE chat_sessions SET title = %s
                        WHERE session_id = %s
                          AND (title IS NULL OR title = '')
                        """,
                        (title, session_id),
                    )
                    updated = cur.rowcount
                conn.commit()
            return updated > 0
        except Exception as exc:
            logger.warning("ConversationStore.set_title_if_empty failed: %s", exc)
            return False

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and (via ON DELETE CASCADE) its messages."""
        return await asyncio.to_thread(self._delete_session, session_id)

    def _delete_session(self, session_id: str) -> bool:
        pool = _get_pool()
        if pool is None:
            return False
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM chat_sessions WHERE session_id = %s",
                        (session_id,),
                    )
                    deleted = cur.rowcount
                conn.commit()
            return deleted > 0
        except Exception as exc:
            logger.warning("ConversationStore.delete_session failed: %s", exc)
            return False

    # ── messages ──────────────────────────────────────────────────

    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        message_id: Optional[str] = None,
    ) -> bool:
        """Append one turn and bump the session's ``updated_at``.

        Returns ``True`` only when a row was actually written, so a replayed
        ``message_id`` reports ``False`` instead of duplicating the turn.
        """
        return await asyncio.to_thread(
            self._append_message, session_id, role, content, message_id
        )

    def _append_message(
        self, session_id: str, role: str, content: str, message_id: Optional[str]
    ) -> bool:
        pool = _get_pool()
        if pool is None:
            return False
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO chat_messages (session_id, message_id, role, content)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (message_id) DO NOTHING
                        """,
                        (session_id, message_id, role, content),
                    )
                    inserted = cur.rowcount > 0
                    cur.execute(
                        "UPDATE chat_sessions SET updated_at = now() WHERE session_id = %s",
                        (session_id,),
                    )
                conn.commit()
            return inserted
        except Exception as exc:
            logger.warning("ConversationStore.append_message failed: %s", exc)
            return False

    async def get_messages(
        self,
        session_id: str,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        """Return the transcript in chronological order (paginated)."""
        return await asyncio.to_thread(self._get_messages, session_id, limit, offset)

    def _get_messages(self, session_id: str, limit: int, offset: int) -> list[dict]:
        pool = _get_pool()
        if pool is None:
            return []
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT role, content, created_at
                        FROM chat_messages
                        WHERE session_id = %s
                        ORDER BY id
                        LIMIT %s OFFSET %s
                        """,
                        (session_id, limit, offset),
                    )
                    rows = cur.fetchall()
            return [
                {"role": row[0], "content": row[1], "created_at": _iso(row[2])}
                for row in rows
            ]
        except Exception as exc:
            logger.warning("ConversationStore.get_messages failed: %s", exc)
            return []

    async def get_recent_messages(self, session_id: str, limit: int = 10) -> list[dict]:
        """Return the last *limit* turns in chronological order.

        This is L0 working memory: what actually goes into the prompt.
        """
        return await asyncio.to_thread(self._get_recent_messages, session_id, limit)

    def _get_recent_messages(self, session_id: str, limit: int) -> list[dict]:
        pool = _get_pool()
        if pool is None:
            return []
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT role, content, created_at FROM (
                            SELECT id, role, content, created_at
                            FROM chat_messages
                            WHERE session_id = %s
                            ORDER BY id DESC
                            LIMIT %s
                        ) recent
                        ORDER BY id
                        """,
                        (session_id, limit),
                    )
                    rows = cur.fetchall()
            return [
                {"role": row[0], "content": row[1], "created_at": _iso(row[2])}
                for row in rows
            ]
        except Exception as exc:
            logger.warning("ConversationStore.get_recent_messages failed: %s", exc)
            return []

    # ── session state ─────────────────────────────────────────────

    async def update_slots(self, session_id: str, slots: dict) -> bool:
        """Persist the merged slot values for a session."""
        return await asyncio.to_thread(self._update_slots, session_id, slots)

    def _update_slots(self, session_id: str, slots: dict) -> bool:
        pool = _get_pool()
        if pool is None:
            return False
        try:
            cleaned = {k: v for k, v in slots.items() if k in _SLOT_FIELDS and v is not None}
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE chat_sessions
                        SET slots = %s::jsonb, updated_at = now()
                        WHERE session_id = %s
                        """,
                        (json.dumps(cleaned, ensure_ascii=False), session_id),
                    )
                    updated = cur.rowcount
                conn.commit()
            return updated > 0
        except Exception as exc:
            logger.warning("ConversationStore.update_slots failed: %s", exc)
            return False

    async def set_plan_request(self, session_id: str, plan_request: Optional[dict]) -> bool:
        """Store (or clear) the request body the session is ready to plan with."""
        return await asyncio.to_thread(self._set_plan_request, session_id, plan_request)

    def _set_plan_request(self, session_id: str, plan_request: Optional[dict]) -> bool:
        pool = _get_pool()
        if pool is None:
            return False
        try:
            payload = (
                json.dumps(plan_request, ensure_ascii=False)
                if plan_request is not None
                else None
            )
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE chat_sessions SET plan_request = %s::jsonb WHERE session_id = %s",
                        (payload, session_id),
                    )
                    updated = cur.rowcount
                conn.commit()
            return updated > 0
        except Exception as exc:
            logger.warning("ConversationStore.set_plan_request failed: %s", exc)
            return False

    async def set_summary(self, session_id: str, summary: Optional[str]) -> bool:
        """Persist the L1 rolling summary of turns that fell out of the window."""
        return await asyncio.to_thread(self._set_summary, session_id, summary)

    def _set_summary(self, session_id: str, summary: Optional[str]) -> bool:
        pool = _get_pool()
        if pool is None:
            return False
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE chat_sessions SET summary = %s WHERE session_id = %s",
                        (summary, session_id),
                    )
                    updated = cur.rowcount
                conn.commit()
            return updated > 0
        except Exception as exc:
            logger.warning("ConversationStore.set_summary failed: %s", exc)
            return False

    async def set_last_plan(self, session_id: str, plan_id: str) -> bool:
        """Link the session to the trip plan it produced."""
        return await asyncio.to_thread(self._set_last_plan, session_id, plan_id)

    def _set_last_plan(self, session_id: str, plan_id: str) -> bool:
        pool = _get_pool()
        if pool is None:
            return False
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE chat_sessions SET last_plan_id = %s WHERE session_id = %s",
                        (plan_id, session_id),
                    )
                    updated = cur.rowcount
                conn.commit()
            return updated > 0
        except Exception as exc:
            logger.warning("ConversationStore.set_last_plan failed: %s", exc)
            return False

    # ── T0.4: Storage visibility ──────────────────────────────────

    async def health(self) -> dict:
        """Report PostgreSQL connectivity for ``/health``. Never raises."""
        return await asyncio.to_thread(self._health)

    def _health(self) -> dict:
        pool = _get_pool()
        if pool is None:
            return {
                "configured": bool(settings.pg_dsn),
                "connected": False,
                "error": _pool_error or "connection pool unavailable",
            }
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return {"configured": True, "connected": True, "error": None}
        except Exception as exc:
            return {
                "configured": True,
                "connected": False,
                "error": f"{type(exc).__name__}: {exc}",
            }


# ── Module-level singleton ───────────────────────────────────────────

conversation_store = ConversationStore()
