"""Supabase CRUD queries for conversations — always filtered by user_id."""
from src.db.client import get_supabase_client
from src.db.models import CONVERSATIONS_TABLE


def create_conversation(user_id: str, data: dict) -> dict:
    db = get_supabase_client()
    row = {
        "user_id": user_id,
        "title": data.get("title", "New Conversation"),
        "model": data.get("model", "llama-3.1-8b-instant"),
        "system_prompt": data.get("system_prompt"),
    }
    result = db.table(CONVERSATIONS_TABLE).insert(row).execute()
    return result.data[0]


def get_conversations(user_id: str, offset: int = 0, limit: int = 20, include_archived: bool = False) -> tuple[list[dict], int]:
    db = get_supabase_client()
    query = db.table(CONVERSATIONS_TABLE).select("*", count="exact").eq("user_id", user_id)

    if not include_archived:
        query = query.eq("is_archived", False)

    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    result = query.execute()
    return result.data, result.count or 0


def get_conversation(conversation_id: str, user_id: str) -> dict | None:
    db = get_supabase_client()
    result = (
        db.table(CONVERSATIONS_TABLE)
        .select("*")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
    return result.data[0] if result.data else None


def update_conversation(conversation_id: str, user_id: str, data: dict) -> dict | None:
    db = get_supabase_client()
    # Filter out None values
    updates = {k: v for k, v in data.items() if v is not None}
    if not updates:
        return get_conversation(conversation_id, user_id)

    result = (
        db.table(CONVERSATIONS_TABLE)
        .update(updates)
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
    return result.data[0] if result.data else None


def delete_conversation(conversation_id: str, user_id: str) -> bool:
    db = get_supabase_client()
    result = (
        db.table(CONVERSATIONS_TABLE)
        .delete()
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
    return len(result.data) > 0


def increment_message_count(conversation_id: str, token_count: int = 0):
    """Increment message_count and total_tokens for a conversation."""
    db = get_supabase_client()
    # Get current values
    result = db.table(CONVERSATIONS_TABLE).select("message_count, total_tokens").eq("id", conversation_id).execute()
    if result.data:
        current = result.data[0]
        db.table(CONVERSATIONS_TABLE).update({
            "message_count": current["message_count"] + 1,
            "total_tokens": current["total_tokens"] + token_count,
        }).eq("id", conversation_id).execute()
