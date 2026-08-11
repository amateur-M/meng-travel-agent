"""Pydantic data models for the CoupleTrip API."""

from datetime import date as DateType, time
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field


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


# ── Core Models ──────────────────────────────────────────────────

class Activity(BaseModel):
    """A single activity within a day's schedule."""

    name: str = Field(..., description="活动名称，如 '洱海骑行'")
    activity_type: ActivityType = Field(..., description="活动类型")
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
    downgrade_applied: bool = Field(default=False, description="是否已降级")
    downgrade_notes: List[str] = Field(default_factory=list)


class TripPlanResponse(BaseModel):
    """Final structured itinerary returned by the agent."""

    plan_id: str = Field(..., description="行程 ID")
    destination: str
    start_date: DateType
    end_date: DateType
    budget_breakdown: BudgetBreakdown
    days: List[DayPlan] = Field(default_factory=list)
    couple_notes: List[str] = Field(default_factory=list, description="情侣寄语汇总")
    status: str = Field(default="completed")


# ── SSE Event Payloads ───────────────────────────────────────────

class SSEEvent(BaseModel):
    """Payload for a single SSE event pushed to the client."""

    phase: str = Field(..., description="当前阶段标识")
    message: str = Field(default="", description="人类可读的进度信息")
    data: Optional[dict] = Field(None, description="阶段产出数据片段")
