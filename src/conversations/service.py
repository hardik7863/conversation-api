"""Business logic for conversations."""
from fastapi import HTTPException

from src.conversations import repository
from src.utils.validators import validate_uuid


def create_conversation(user_id: str, data: dict) -> dict:
    return repository.create_conversation(user_id, data)


def get_conversations(user_id: str, page: int, limit: int, include_archived: bool = False) -> dict:
    from src.utils.validators import get_pagination_params
    offset, limit = get_pagination_params(page, limit)

    conversations, total = repository.get_conversations(user_id, offset, limit, include_archived)
    return {
        "conversations": conversations,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": offset + limit < total,
    }


def get_conversation(conversation_id: str, user_id: str) -> dict:
    validate_uuid(conversation_id, "conversation_id")
    conversation = repository.get_conversation(conversation_id, user_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def update_conversation(conversation_id: str, user_id: str, data: dict) -> dict:
    validate_uuid(conversation_id, "conversation_id")
    conversation = repository.update_conversation(conversation_id, user_id, data)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def delete_conversation(conversation_id: str, user_id: str) -> bool:
    validate_uuid(conversation_id, "conversation_id")
    deleted = repository.delete_conversation(conversation_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return True
