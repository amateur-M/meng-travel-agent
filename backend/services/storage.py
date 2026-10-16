"""PlanStore — PostgreSQL persistence layer for trip plans (P0.1).

Stores plan records (request + response + status) in a single ``plans`` table.
The response payload is kept as JSONB so the full TripPlanResponse can be
recovered verbatim — this is what powers the "refresh /result?plan_id=xxx"
recovery flow.

Design notes:
  - Uses ``psycopg`` with a ``ConnectionPool`` for connection reuse.
  - DDL is idempotent (CREATE TABLE IF NOT EXISTS) and auto-runs on first use.
  - When PG_DSN points to an unreachable server (e.g. tests without Docker),
    every method degrades gracefully: ``save`` / ``update`` / ``delete``
    become no-ops and ``get`` / ``list`` return ``None`` / ``[]``.  This
    keeps the 183 existing tests green without requiring a live Postgres.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List

import psycopg
from psycopg_pool import ConnectionPool

from config.settings import settings

logger = logging.getLogger("coupletrip")

# ── Connection pool (lazy singleton) ──────────────────────────────────

_pool: Optional[ConnectionPool] = None
_pool_unavailable = False
_pool_error: Optional[str] = None


def _get_pool() -> Optional[ConnectionPool]:
    """Return the shared connection pool, initialising it on first call.

    If the database is unreachable, marks itself unavailable so subsequent
    calls skip silently instead of retrying on every request.  The reason is
    kept in ``_pool_error`` so ``health()`` can report *why* rather than
    leaving operators to guess (T0.4: the silent degradation here previously
    hid a local misconfiguration for the whole V2 cycle).
    """
    global _pool, _pool_unavailable, _pool_error
    if _pool is not None:
        return _pool
    if _pool_unavailable:
        return None

    pool: Optional[ConnectionPool] = None
    try:
        # Open explicitly rather than via open=True: when the constructor
        # raises, the half-built pool's worker threads would otherwise be
        # left running (psycopg_pool warns "couldn't stop thread ...").
        pool = ConnectionPool(
            conninfo=settings.pg_dsn,
            min_size=1,
            max_size=5,
            open=False,
        )
        # Fail fast: the psycopg_pool default is 30s, which would stall
        # /health and every request behind an unreachable database.
        pool.open(wait=True, timeout=5)
        # Verify connectivity + ensure table exists
        with pool.connection() as conn:
            _init_ddl(conn)
        _pool = pool
        _pool_error = None
        logger.info("PlanStore: PostgreSQL pool initialised")
        return pool
    except Exception as exc:
        _pool_error = f"{type(exc).__name__}: {exc}"
        logger.warning("PlanStore: PostgreSQL unavailable — persistence disabled: %s", exc)
        if pool is not None:
            try:
                pool.close()
            except Exception:  # pragma: no cover - best-effort cleanup
                pass
        _pool_unavailable = True
        return None


def _init_ddl(conn) -> None:
    """Create the ``plans`` table if it doesn't exist (idempotent)."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                plan_id      TEXT PRIMARY KEY,
                request      JSONB NOT NULL,
                response     JSONB,
                status       TEXT NOT NULL DEFAULT 'processing',
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_plans_created_at
            ON plans (created_at DESC)
        """)
        # P2.3: feedback table for user thumbs up/down on activities
        cur.execute("""
            CREATE TABLE IF NOT EXISTS plan_feedback (
                id           SERIAL PRIMARY KEY,
                plan_id      TEXT NOT NULL,
                activity_name TEXT NOT NULL,
                thumbs       TEXT NOT NULL CHECK (thumbs IN ('up', 'down')),
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_plan_id
            ON plan_feedback (plan_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_activity
            ON plan_feedback (activity_name)
        """)
    conn.commit()


# ── PlanStore ─────────────────────────────────────────────────────────

class PlanStore:
    """CRUD interface for trip-plan records backed by PostgreSQL."""

    def save(self, plan_id: str, request: dict, response: Optional[dict] = None,
             status: str = "processing") -> bool:
        """Insert a new plan record (or upsert if plan_id exists)."""
        pool = _get_pool()
        if pool is None:
            return False
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO plans (plan_id, request, response, status)
                        VALUES (%s, %s::jsonb, %s::jsonb, %s)
                        ON CONFLICT (plan_id) DO UPDATE
                            SET request   = EXCLUDED.request,
                                response  = COALESCE(EXCLUDED.response, plans.response),
                                status    = EXCLUDED.status,
                                updated_at = now()
                    """, (
                        plan_id,
                        json.dumps(request, ensure_ascii=False),
                        json.dumps(response, ensure_ascii=False) if response is not None else None,
                        status,
                    ))
                conn.commit()
            return True
        except Exception as exc:
            logger.warning("PlanStore.save failed: %s", exc)
            return False

    def update(self, plan_id: str, response: dict, status: str = "completed") -> bool:
        """Update an existing plan record with the final response + status."""
        pool = _get_pool()
        if pool is None:
            return False
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE plans
                        SET response = %s::jsonb,
                            status   = %s,
                            updated_at = now()
                        WHERE plan_id = %s
                    """, (
                        json.dumps(response, ensure_ascii=False),
                        status,
                        plan_id,
                    ))
                conn.commit()
            return True
        except Exception as exc:
            logger.warning("PlanStore.update failed: %s", exc)
            return False

    def get(self, plan_id: str) -> Optional[dict]:
        """Return the full plan record, or ``None`` if not found / DB down."""
        pool = _get_pool()
        if pool is None:
            return None
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT plan_id, request, response, status, created_at, updated_at
                        FROM plans
                        WHERE plan_id = %s
                    """, (plan_id,))
                    row = cur.fetchone()
            if row is None:
                return None
            return {
                "plan_id": row[0],
                "request": row[1],
                "response": row[2],
                "status": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
                "updated_at": row[5].isoformat() if row[5] else None,
            }
        except Exception as exc:
            logger.warning("PlanStore.get failed: %s", exc)
            return None

    def list(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """Return a paginated list of plan summaries, newest first."""
        pool = _get_pool()
        if pool is None:
            return []
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT plan_id, request->>'destination' AS destination,
                               request->>'start_date' AS start_date,
                               request->>'end_date' AS end_date,
                               status, created_at
                        FROM plans
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """, (limit, offset))
                    rows = cur.fetchall()
            return [
                {
                    "plan_id": row[0],
                    "destination": row[1],
                    "start_date": row[2],
                    "end_date": row[3],
                    "status": row[4],
                    "created_at": row[5].isoformat() if row[5] else None,
                }
                for row in rows
            ]
        except Exception as exc:
            logger.warning("PlanStore.list failed: %s", exc)
            return []

    def delete(self, plan_id: str) -> bool:
        """Delete a plan record. Returns True if a row was actually deleted."""
        pool = _get_pool()
        if pool is None:
            return False
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM plans WHERE plan_id = %s", (plan_id,))
                    deleted = cur.rowcount
                conn.commit()
            return deleted > 0
        except Exception as exc:
            logger.warning("PlanStore.delete failed: %s", exc)
            return False

    # ── T0.4: Storage visibility ──────────────────────────────────

    def health(self) -> dict:
        """Report PostgreSQL connectivity for ``/health``.

        Never raises. Reports the recorded reason when the pool could not be
        created, so a misconfiguration is visible instead of showing up only
        as persistence silently doing nothing.
        """
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

    # ── P2.3: Feedback ────────────────────────────────────────────

    def save_feedback(self, plan_id: str, activity_name: str, thumbs: str) -> bool:
        """Record a thumbs up/down for a specific activity in a plan."""
        pool = _get_pool()
        if pool is None:
            return False
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO plan_feedback (plan_id, activity_name, thumbs)
                        VALUES (%s, %s, %s)
                    """, (plan_id, activity_name, thumbs))
                conn.commit()
            return True
        except Exception as exc:
            logger.warning("PlanStore.save_feedback failed: %s", exc)
            return False

    def list_feedback(self, activity_name: Optional[str] = None) -> List[dict]:
        """Return aggregated feedback counts, optionally filtered by activity name.

        Returns a list of {activity_name, up, down} dicts.
        """
        pool = _get_pool()
        if pool is None:
            return []
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    if activity_name:
                        cur.execute("""
                            SELECT activity_name,
                                   COUNT(*) FILTER (WHERE thumbs = 'up') AS up,
                                   COUNT(*) FILTER (WHERE thumbs = 'down') AS down
                            FROM plan_feedback
                            WHERE activity_name = %s
                            GROUP BY activity_name
                        """, (activity_name,))
                    else:
                        cur.execute("""
                            SELECT activity_name,
                                   COUNT(*) FILTER (WHERE thumbs = 'up') AS up,
                                   COUNT(*) FILTER (WHERE thumbs = 'down') AS down
                            FROM plan_feedback
                            GROUP BY activity_name
                        """)
                    rows = cur.fetchall()
            return [
                {"activity_name": row[0], "up": int(row[1]), "down": int(row[2])}
                for row in rows
            ]
        except Exception as exc:
            logger.warning("PlanStore.list_feedback failed: %s", exc)
            return []


# ── Module-level singleton ────────────────────────────────────────────

plan_store = PlanStore()


def generate_plan_id() -> str:
    """Generate a URL-safe plan ID."""
    return uuid.uuid4().hex
