"""Tests for Pydantic schemas — request/response models."""

import pytest
from datetime import date
from pydantic import ValidationError

from schemas import (
    TripPlanRequest, TripPlanResponse,
    Activity, DayPlan, BudgetBreakdown, SSEEvent,
    Pace, Period, ActivityType,
)


class TestTripPlanRequest:
    """POST /api/plan request validation."""

    def test_valid_request(self):
        req = TripPlanRequest(
            origin="北京",
            destination="大理",
            start_date="2026-09-01",
            end_date="2026-09-03",
            budget=5000,
        )
        assert req.origin == "北京"
        assert req.budget == 5000
        assert req.pace == Pace.relaxed
        assert req.preferences == ["浪漫", "美食"]

    def test_default_preferences_and_pace(self):
        req = TripPlanRequest(
            origin="上海",
            destination="丽江",
            start_date="2026-10-01",
            end_date="2026-10-05",
            budget=8000,
        )
        assert req.preferences == ["浪漫", "美食"]
        assert req.pace == Pace.relaxed

    def test_custom_pace(self):
        req = TripPlanRequest(
            origin="成都",
            destination="三亚",
            start_date="2026-11-01",
            end_date="2026-11-03",
            budget=6000,
            pace=Pace.packed,
            preferences=["冒险", "户外"],
        )
        assert req.pace == Pace.packed
        assert "冒险" in req.preferences

    def test_budget_must_be_positive(self):
        with pytest.raises(ValidationError):
            TripPlanRequest(
                origin="北京",
                destination="大理",
                start_date="2026-09-01",
                end_date="2026-09-03",
                budget=0,
            )

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            TripPlanRequest(
                origin="北京",
            )


class TestActivity:
    """Activity model validation."""

    def test_minimal_activity(self):
        a = Activity(
            name="洱海骑行",
            activity_type=ActivityType.outdoor,
            period=Period.morning,
        )
        assert a.name == "洱海骑行"
        assert a.duration_min == 60
        assert a.estimated_cost == 0.0

    def test_full_activity(self):
        a = Activity(
            name="段公子餐厅",
            activity_type=ActivityType.dining,
            period=Period.afternoon,
            start_time="12:00",
            duration_min=90,
            description="品尝地道云南菜",
            estimated_cost=160,
            location="大理古城人民路",
            couple_note="和你一起吃，连白米饭都是甜的",
        )
        assert a.estimated_cost == 160
        assert a.location == "大理古城人民路"


class TestDayPlan:
    """DayPlan model validation."""

    def test_empty_day(self):
        d = DayPlan(day_index=0, trip_date=date(2026, 9, 1))
        assert d.weather_condition == "晴"
        assert d.daily_cost == 0.0
        assert d.activities == []

    def test_day_with_activities(self):
        d = DayPlan(
            day_index=1,
            trip_date=date(2026, 9, 2),
            weather_condition="多云",
            activities=[
                Activity(name="古城漫步", activity_type=ActivityType.sightseeing, period=Period.morning),
            ],
            daily_cost=80,
        )
        assert len(d.activities) == 1
        assert d.daily_cost == 80


class TestBudgetBreakdown:
    """BudgetBreakdown model validation."""

    def test_under_budget(self):
        b = BudgetBreakdown(total_budget=5000, total_spent=3200)
        assert b.over_budget is False
        assert b.downgrade_applied is False

    def test_over_budget(self):
        b = BudgetBreakdown(
            total_budget=5000,
            total_spent=6200,
            over_budget=True,
            downgrade_applied=True,
            downgrade_notes=["替换苍山索道为免费观景台"],
        )
        assert b.over_budget is True
        assert len(b.downgrade_notes) == 1


class TestTripPlanResponse:
    """Final response model validation."""

    def test_minimal_response(self):
        resp = TripPlanResponse(
            plan_id="abc12345",
            destination="大理",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 3),
            budget_breakdown=BudgetBreakdown(total_budget=5000, total_spent=3200),
        )
        assert resp.status == "completed"
        assert resp.plan_id == "abc12345"

    def test_full_response_with_days(self):
        resp = TripPlanResponse(
            plan_id="xyz67890",
            destination="丽江",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
            budget_breakdown=BudgetBreakdown(total_budget=4000, total_spent=2800),
            days=[
                DayPlan(day_index=0, trip_date=date(2026, 10, 1)),
                DayPlan(day_index=1, trip_date=date(2026, 10, 2)),
            ],
            couple_notes=["在丽江遇见最美的你"],
        )
        assert len(resp.days) == 2


class TestSSEEvent:
    """SSE event payload model."""

    def test_step_event(self):
        e = SSEEvent(phase="parse_input", message="正在解析需求...")
        assert e.phase == "parse_input"
        assert e.data is None

    def test_event_with_data(self):
        e = SSEEvent(
            phase="complete",
            message="行程生成完毕",
            data={"plan_id": "abc", "status": "completed"},
        )
        assert e.data["plan_id"] == "abc"
