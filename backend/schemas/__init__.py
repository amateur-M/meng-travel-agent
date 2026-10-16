"""Pydantic data models for the CoupleTrip API."""

from datetime import date as DateType, time
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


# ── Enums ────────────────────────────────────────────────────────

class Pace(str, Enum):
    relaxed = "轻松"
    moderate = "适中"
    packed = "充实"


class Period(str, Enum):
    morning = "上午"
    afternoon = "下午"
    evening = "晚间"


class ActivityType(str, Enum):
    sightseeing = "景点"
    dining = "美食"
    indoor = "室内"
    outdoor = "户外"
    culture = "文化"
    adventure = "冒险"
    rest = "留白"
    # P8: added missing types produced by poi_search_tool / _mock_itinerary
    nature = "自然"
    humanities = "人文"
    trendy = "网红"


# ── Request ──────────────────────────────────────────────────────

class TripPlanRequest(BaseModel):
    """Request body for POST /api/plan."""

    origin: str = Field(..., description="出发地，如 '北京'")
    destination: str = Field(..., description="目的地，如 '大理'")
    start_date: DateType = Field(..., description="出发日期")
    end_date: DateType = Field(..., description="返程日期")
    budget: float = Field(..., gt=0, description="总预算（元）")
    preferences: List[str] = Field(
        default_factory=lambda: ["浪漫", "美食"],
        description="偏好标签"
    )
    pace: Pace = Field(default=Pace.relaxed, description="行程节奏")
    session_id: Optional[str] = Field(
        None,
        description="发起规划的对话会话 ID（V3/P1）；传入后该会话会记住本次行程",
    )


# ── Core Models ──────────────────────────────────────────────────

class Activity(BaseModel):
    """A single activity within a day's schedule.

    P8: field renamed from ``activity_type`` to ``type`` to match the key
    actually produced by graph nodes and consumed by the frontend.
    ``populate_by_name=True`` allows both ``type=`` and ``activity_type=``
    for backward compatibility with existing test fixtures.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., description="活动名称，如 '洱海骑行'")
    type: ActivityType = Field(
        ...,
        alias="activity_type",
        description="活动类型",
    )
    period: Period = Field(..., description="所属时段")
    start_time: Optional[str] = Field(None, description="开始时间 HH:MM")
    duration_min: int = Field(default=60, description="预估耗时（分钟）")
    description: str = Field(default="", description="活动简介")
    estimated_cost: float = Field(default=0.0, description="预估花费（元）")
    location: Optional[str] = Field(None, description="地点名/地址")
    weather_note: Optional[str] = Field(None, description="天气提示")
    couple_note: Optional[str] = Field(None, description="情侣寄语")
    indoor_backup: Optional[str] = Field(None, description="室内备选方案")


class DayPlan(BaseModel):
    """One day's itinerary."""

    day_index: int = Field(..., description="第几天（0-based）")
    trip_date: DateType = Field(..., description="日期")
    weather_condition: str = Field(default="晴", description="天气概况")
    weather_high: Optional[float] = Field(None, description="最高温度")
    weather_low: Optional[float] = Field(None, description="最低温度")
    activities: List[Activity] = Field(default_factory=list)
    daily_cost: float = Field(default=0.0, description="当日累计花费")
    day_note: Optional[str] = Field(None, description="当日总结寄语")


class BudgetBreakdown(BaseModel):
    """Transparent budget summary."""

    total_budget: float = Field(..., description="总预算")
    total_spent: float = Field(..., description="总花费")
    by_day: List[float] = Field(default_factory=list, description="每日花费")
    over_budget: bool = Field(default=False)
    warning_level: str = Field(default="ok", description="预算状态: ok / warning / over")
    spending_ratio: float = Field(default=0.0, description="预算使用比例")
    downgrade_applied: bool = Field(default=False, description="是否已降级")
    downgrade_notes: List[str] = Field(default_factory=list)


class WeatherSwap(BaseModel):
    """A weather-driven itinerary adjustment shown in the UI."""

    day_index: int = Field(..., description="第几天（0-based）")
    original_name: str = Field(..., description="原活动名称")
    replacement_name: str = Field(..., description="调整后活动名称")
    reason: str = Field(default="", description="调整原因")
    adjustment_type: str = Field(default="swap", description="swap / time_shift")


class RhythmAdjustment(BaseModel):
    """A rhythm-control adjustment (M5): cap over-dense periods or inject rest."""

    day_index: int = Field(..., description="第几天（0-based）")
    period: str = Field(default="", description="时段：上午/下午/晚间")
    kind: str = Field(default="", description="cap / inject_rest")
    reason: str = Field(default="", description="调整原因")
    dropped: Optional[List[str]] = Field(None, description="被裁剪的活动名称（kind=cap 时）")


class TripPlanResponse(BaseModel):
    """Final structured itinerary returned by the agent."""

    plan_id: str = Field(..., description="行程 ID")
    destination: str
    start_date: DateType
    end_date: DateType
    budget_breakdown: BudgetBreakdown
    days: List[DayPlan] = Field(default_factory=list)
    couple_notes: List[str] = Field(default_factory=list, description="情侣寄语汇总")
    weather_swaps: List[WeatherSwap] = Field(
        default_factory=list,
        description="天气自适应调整记录",
    )
    rhythm_adjustments: List[RhythmAdjustment] = Field(
        default_factory=list,
        description="M5 节奏控制调整记录（裁剪/留白注入）",
    )
    status: str = Field(default="completed")


# ── SSE Event Payloads ───────────────────────────────────────────

class SSEEvent(BaseModel):
    """Payload for a single SSE event pushed to the client."""

    phase: str = Field(..., description="当前阶段标识")
    message: str = Field(default="", description="人类可读的进度信息")
    data: Optional[dict] = Field(None, description="阶段产出数据片段")
