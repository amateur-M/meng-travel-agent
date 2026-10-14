"""Pydantic models for the conversational chat API (P1.1)."""

from typing import Optional, List, Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""

    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话 ID，首次可不传")


class Slots(BaseModel):
    """Extracted trip-planning slot values."""

    destination: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    budget: Optional[float] = None
    origin: Optional[str] = None
    preferences: Optional[List[str]] = None
    pace: Optional[str] = None


class ModifyPatch(BaseModel):
    """Incremental modification to an existing plan request (P1.2)."""

    destination: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    budget: Optional[float] = None
    origin: Optional[str] = None
    preferences: Optional[List[str]] = None
    pace: Optional[str] = None


class ChatReply(BaseModel):
    """Response from POST /api/chat."""

    session_id: str = Field(..., description="会话 ID")
    reply: str = Field(..., description="助手回复文本")
    intent: str = Field(
        ...,
        description="识别的意图: greeting / question / planning_intent / planning_ready / modify_plan",
    )
    slots: Slots = Field(default_factory=Slots, description="当前已收集的槽位")
    ready: bool = Field(default=False, description="槽位是否已满，可触发规划")
    plan_request: Optional[dict] = Field(
        None,
        description="当 ready=true 时，可直接喂 POST /api/plan 的请求体",
    )
    modify_patch: Optional[ModifyPatch] = Field(
        None,
        description="当 intent=modify_plan 时，包含增量修改 patch (P1.2)",
    )
