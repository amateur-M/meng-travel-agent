"""Tests for PlanStore (P0.1 行程持久化).

When PostgreSQL is unavailable (no Docker / no live DB in CI), the store
should degrade gracefully — every method returns a safe fallback instead
of raising.  These tests verify that graceful degradation path.

A separate integration test (marked with a marker that requires a live DB)
can be added later for the happy path.
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

    def test_save_returns_false_without_db(self, monkeypatch):
        # Force pool to be unavailable
        monkeypatch.setattr("services.storage._pool_unavailable", True)
        store = PlanStore()
        result = store.save("test-id", {"destination": "大理"})
        assert result is False

    def test_update_returns_false_without_db(self, monkeypatch):
        monkeypatch.setattr("services.storage._pool_unavailable", True)
        store = PlanStore()
        result = store.update("test-id", {"days": []})
        assert result is False

    def test_get_returns_none_without_db(self, monkeypatch):
        monkeypatch.setattr("services.storage._pool_unavailable", True)
        store = PlanStore()
        result = store.get("nonexistent-id")
        assert result is None

    def test_list_returns_empty_without_db(self, monkeypatch):
        monkeypatch.setattr("services.storage._pool_unavailable", True)
        store = PlanStore()
        result = store.list()
        assert result == []

    def test_delete_returns_false_without_db(self, monkeypatch):
        monkeypatch.setattr("services.storage._pool_unavailable", True)
        store = PlanStore()
        result = store.delete("nonexistent-id")
        assert result is False
