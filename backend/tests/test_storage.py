"""Tests for PlanStore (P0.1 行程持久化).

When PostgreSQL is unavailable the store degrades gracefully instead of
raising: every method returns a safe fallback.

These tests rely on the suite-wide ``_isolate_from_real_database`` fixture
(see conftest.py), which is what makes them environment-independent. Clearing
only the ``_unavailable`` flag (as this file originally did) left them passing
*only* on a machine with no database, and failing as soon as one was running:
a test that depends on the environment cannot prove anything about the degraded
path.

The happy path is covered by tests/test_storage_pg.py.
"""

import pytest

from services.storage import PlanStore, generate_plan_id


class TestPlanStoreDegraded:
    """With no live PostgreSQL, all methods should degrade safely."""

    def test_generate_plan_id_returns_hex_string(self):
        pid = generate_plan_id()
        assert isinstance(pid, str)
        assert len(pid) == 32  # uuid4 hex

    def test_generate_plan_id_unique(self):
        ids = {generate_plan_id() for _ in range(100)}
        assert len(ids) == 100

    def test_save_returns_false_without_db(self):
        result = PlanStore().save("test-id", {"destination": "大理"})
        assert result is False

    def test_update_returns_false_without_db(self):
        result = PlanStore().update("test-id", {"days": []})
        assert result is False

    def test_get_returns_none_without_db(self):
        assert PlanStore().get("nonexistent-id") is None

    def test_list_returns_empty_without_db(self):
        assert PlanStore().list() == []

    def test_delete_returns_false_without_db(self):
        assert PlanStore().delete("nonexistent-id") is False

    def test_save_feedback_returns_false_without_db(self):
        assert PlanStore().save_feedback("p1", "洱海骑行", "up") is False

    def test_list_feedback_returns_empty_without_db(self):
        assert PlanStore().list_feedback() == []

    def test_health_reports_disconnected(self):
        health = PlanStore().health()
        assert health["connected"] is False
        assert health["error"], "a disconnected store must explain why"
