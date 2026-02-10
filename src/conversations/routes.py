"""Conversation CRUD routes."""
from fastapi import APIRouter, Depends, Query

from src.auth.dependencies import get_current_user
from src.conversations import service
from src.conversations.schemas import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
)
from src.middleware.rate_limiter import standard_rate_limit

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post("", status_code=201, response_model=ConversationResponse)
async def create_conversation(
    body: ConversationCreate,
    current_user: dict = Depends(get_current_user),
    _rate=Depends(standard_rate_limit),
):
    """Create a new conversation."""
    conversation = service.create_conversation(
        user_id=current_user["id"],
        data=body.model_dump(),
    )
    return conversation


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    include_archived: bool = Query(default=False),
    current_user: dict = Depends(get_current_user),
    _rate=Depends(standard_rate_limit),
):
    """List user's conversations with pagination."""
    return service.get_conversations(
        user_id=current_user["id"],
        page=page,
        limit=limit,
        include_archived=include_archived,
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    _rate=Depends(standard_rate_limit),
):
    """Get a specific conversation."""
    return service.get_conversation(conversation_id, current_user["id"])


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    body: ConversationUpdate,
    current_user: dict = Depends(get_current_user),
    _rate=Depends(standard_rate_limit),
):
    """Update a conversation (title, model, system_prompt, archive)."""
    return service.update_conversation(
        conversation_id,
        current_user["id"],
        body.model_dump(exclude_unset=True),
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    _rate=Depends(standard_rate_limit),
):
    """Delete a conversation and all its messages."""
    service.delete_conversation(conversation_id, current_user["id"])
    return None
