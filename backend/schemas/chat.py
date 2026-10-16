"""Pydantic models for the conversational chat API (P1.1)."""

from typing import Optional, List, Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""

    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话 ID，首次可不传")
    client_id: Optional[str] = Field(
        None,
        description="浏览器侧稳定 id（localStorage），用于按客户端隔离会话与画像",
    )
    message_id: Optional[str] = Field(
        None,
        description="客户端生成的轮次 id；同 id 重试不会重复写入（幂等）",
    )


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


class SessionSummary(BaseModel):
    """One row of the conversation list (V3/P1)."""

    session_id: str
    title: Optional[str] = None
    updated_at: Optional[str] = None
    last_plan_id: Optional[str] = None
    message_count: int = 0
    preview: str = ""


class SessionListResponse(BaseModel):
    """Paginated conversation list."""

    page: int
    size: int
    items: List[SessionSummary]


class SessionDetail(BaseModel):
    """Session metadata for hydrate-on-refresh (V3/P1)."""

    session_id: str
    title: Optional[str] = None
    summary: Optional[str] = None
    slots: Slots = Field(default_factory=Slots)
    plan_request: Optional[dict] = None
    last_plan_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int = 0


class ChatMessageItem(BaseModel):
    """One stored turn."""

    role: str
    content: str
    created_at: Optional[str] = None


class MessageListResponse(BaseModel):
    """Transcript page, chronological."""

    session_id: str
    page: int
    size: int
    total: int
    items: List[ChatMessageItem]


class RenameSessionRequest(BaseModel):
    """Body for PATCH /api/chat/sessions/{id}."""

    title: str = Field(..., min_length=1, max_length=60, description="新的会话标题")
