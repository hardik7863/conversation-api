"""Pydantic schemas for conversations."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(default="New Conversation", max_length=255)
    model: Optional[str] = Field(default="llama-3.1-8b-instant", max_length=100)
    system_prompt: Optional[str] = Field(default=None, max_length=4000)


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    model: Optional[str] = Field(default=None, max_length=100)
    system_prompt: Optional[str] = Field(default=None, max_length=4000)
    is_archived: Optional[bool] = None


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    model: str
    system_prompt: Optional[str] = None
    is_archived: bool
    total_tokens: int
    message_count: int
    metadata: dict = {}
    created_at: str
    updated_at: str


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
    total: int
    page: int
    limit: int
    has_more: bool
