"""Real PostgreSQL round-trip for PlanStore (P0.1 plans + P2.3 feedback).

Mirrors ``test_conversation_store_pg.py``: skips **loudly** when the database is
unreachable, so a missing verification is visible rather than silently passing.
The V2 cycle shipped this store with every method returning False and no test
that could notice.

Note on cleanup: ``plan_feedback`` rows are deliberately *not* linked to
``plans`` by a foreign key (feedback is knowledge about an activity, and stays
useful after the plan row is gone), so deleting the plan does not remove them.
The test therefore removes its own feedback rows explicitly.

Text in this file is kept ASCII-only on purpose: a Windows checkout may have a
legacy console code page, and non-ASCII punctuation in source has already been
mangled once by tooling here (see BOOTSTRAP's environment notes).
"""

import uuid

import psycopg
import pytest

# These tests exist to verify the real database, so they opt out of the
# suite-wide isolation fixture in tests/conftest.py.
pytestmark = pytest.mark.real_database

from config.settings import settings
from services.storage import plan_store


def _require_database() -> None:
    health = plan_store.health()
    if not health["connected"]:
        pytest.skip(
            "PostgreSQL unavailable - plan persistence NOT verified "
            f"(reason: {health['error']}). Run backend/scripts/init_local_db.sql."
        )


def _cleanup_feedback(plan_id: str) -> None:
    with psycopg.connect(settings.pg_dsn, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM plan_feedback WHERE plan_id = %s", (plan_id,))
        conn.commit()


def test_plan_store_round_trip():
    _require_database()

    plan_id = f"pytest-plan-{uuid.uuid4().hex}"
    try:
        # create
        assert plan_store.save(
            plan_id, {"destination": "Dali", "budget": 5000}, status="processing"
        ) is True

        record = plan_store.get(plan_id)
        assert record is not None
        assert record["status"] == "processing"
        assert record["request"]["destination"] == "Dali"
        assert record["response"] is None, "nothing produced yet"

        # complete
        assert plan_store.update(
            plan_id, {"destination": "Dali", "days": []}, status="completed"
        ) is True

        record = plan_store.get(plan_id)
        assert record["status"] == "completed"
        assert record["response"]["destination"] == "Dali"

        # listed for /api/plan/history
        row = next((r for r in plan_store.list(limit=50) if r["plan_id"] == plan_id), None)
        assert row is not None, "a saved plan must appear in the history list"
        assert row["destination"] == "Dali"
        assert row["status"] == "completed"

        # upsert keeps the previously stored response
        assert plan_store.save(
            plan_id, {"destination": "Sanya"}, status="processing"
        ) is True
        record = plan_store.get(plan_id)
        assert record["request"]["destination"] == "Sanya"
        assert record["response"] is not None, (
            "COALESCE(EXCLUDED.response, plans.response) must not erase the "
            "stored itinerary when the request is re-saved"
        )

        # feedback aggregation (P2.3 / L3)
        liked = f"activity-up-{uuid.uuid4().hex[:8]}"
        disliked = f"activity-down-{uuid.uuid4().hex[:8]}"
        assert plan_store.save_feedback(plan_id, liked, "up") is True
        assert plan_store.save_feedback(plan_id, liked, "up") is True
        assert plan_store.save_feedback(plan_id, disliked, "down") is True

        aggregated = {f["activity_name"]: f for f in plan_store.list_feedback()}
        assert aggregated[liked]["up"] == 2
        assert aggregated[liked]["down"] == 0
        assert aggregated[disliked]["down"] == 1

        filtered = plan_store.list_feedback(liked)
        assert len(filtered) == 1 and filtered[0]["up"] == 2

        # delete
        assert plan_store.delete(plan_id) is True
        assert plan_store.get(plan_id) is None
        assert plan_store.delete(plan_id) is False, "second delete is a no-op"
    finally:
        plan_store.delete(plan_id)
        _cleanup_feedback(plan_id)


def test_health_reports_connected_state():
    """Whatever the environment, health() must answer without raising."""
    health = plan_store.health()
    assert set(health) == {"configured", "connected", "error"}
    if not health["connected"]:
        assert health["error"], "a disconnected store must explain why"
