"""Pydantic schemas for messages."""
from typing import Optional

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=32000)
    thinking_enabled: bool = Field(default=False)


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    token_count: int
    model: Optional[str] = None
    finish_reason: Optional[str] = None
    latency_ms: Optional[int] = None
    cost_estimate: float = 0
    thinking_enabled: bool = False
    metadata: dict = {}
    created_at: str


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    total: int
    page: int
    limit: int
    has_more: bool
