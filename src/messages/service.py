"""Message service — orchestrates context building, LLM calls, persistence, cost tracking."""
import logging
import threading
import time

from src.conversations import repository as conv_repo
from src.db.client import get_supabase_client
from src.db.models import MESSAGES_TABLE, CONVERSATIONS_TABLE
from src.llm import client as llm_client
from src.llm.context import build_context
from src.llm.prompts import DEFAULT_SYSTEM_PROMPT, THINKING_MODE_ADDON
from src.llm.token_counter import count_tokens
from src.utils.cost_tracker import calculate_cost

logger = logging.getLogger(__name__)


def get_messages(conversation_id: str, page: int = 1, limit: int = 50) -> dict:
    """Get paginated messages for a conversation."""
    from src.utils.validators import get_pagination_params
    offset, limit = get_pagination_params(page, limit)

    db = get_supabase_client()
    result = (
        db.table(MESSAGES_TABLE)
        .select("*", count="exact")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .range(offset, offset + limit - 1)
        .execute()
    )
    total = result.count or 0
    return {
        "messages": result.data,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": offset + limit < total,
    }


def _get_conversation_messages(conversation_id: str) -> list[dict]:
    """Get all messages for context building."""
    db = get_supabase_client()
    result = (
        db.table(MESSAGES_TABLE)
        .select("role, content")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data


def _persist_message(
    conversation_id: str,
    role: str,
    content: str,
    token_count: int = 0,
    model: str | None = None,
    finish_reason: str | None = None,
    latency_ms: int | None = None,
    cost_estimate: float = 0,
    thinking_enabled: bool = False,
    metadata: dict | None = None,
) -> dict:
    """Save a message to the database."""
    db = get_supabase_client()
    row = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "token_count": token_count,
        "cost_estimate": cost_estimate,
        "thinking_enabled": thinking_enabled,
        "metadata": metadata or {},
    }
    # Only include optional fields when they have values
    if model is not None:
        row["model"] = model
    if finish_reason is not None:
        row["finish_reason"] = finish_reason
    if latency_ms is not None:
        row["latency_ms"] = latency_ms

    try:
        result = db.table(MESSAGES_TABLE).insert(row).execute()
    except Exception as e:
        # Fallback: if new columns don't exist yet, retry without them
        if "PGRST204" in str(e):
            row.pop("finish_reason", None)
            row.pop("latency_ms", None)
            result = db.table(MESSAGES_TABLE).insert(row).execute()
        else:
            raise
    return result.data[0]


def _trigger_auto_title(conversation_id: str, first_message: str):
    """Generate and set a title for the conversation (runs in background thread)."""
    try:
        title = llm_client.generate_title(first_message)
        db = get_supabase_client()
        db.table(CONVERSATIONS_TABLE).update({"title": title}).eq("id", conversation_id).execute()
        logger.info(f"Auto-titled conversation {conversation_id}: {title}")
    except Exception as e:
        logger.warning(f"Auto-title failed for {conversation_id}: {e}")


def send_message(
    conversation_id: str,
    content: str,
    thinking_enabled: bool = False,
    conversation: dict | None = None,
) -> dict:
    """
    Send a message, get LLM response, persist both, track cost.
    Returns the assistant message.
    """
    if conversation is None:
        conversation = conv_repo.get_conversation(conversation_id, user_id=None)

    # Get system prompt
    system_prompt = conversation.get("system_prompt") or DEFAULT_SYSTEM_PROMPT
    if thinking_enabled:
        system_prompt += THINKING_MODE_ADDON

    model = conversation.get("model", "llama-3.1-8b-instant")

    # Persist user message
    user_tokens = count_tokens(content)
    user_msg = _persist_message(
        conversation_id=conversation_id,
        role="user",
        content=content,
        token_count=user_tokens,
        thinking_enabled=thinking_enabled,
    )

    # Build context
    history = _get_conversation_messages(conversation_id)
    context = build_context(history, system_prompt, model=model)

    # Call LLM with latency tracking
    start_time = time.monotonic()
    response = llm_client.chat_completion(context, model=model)
    latency_ms = int((time.monotonic() - start_time) * 1000)

    # Calculate cost
    cost = calculate_cost(
        model=response["model"],
        prompt_tokens=response["usage"]["prompt_tokens"],
        completion_tokens=response["usage"]["completion_tokens"],
    )

    # Persist assistant message
    assistant_msg = _persist_message(
        conversation_id=conversation_id,
        role="assistant",
        content=response["content"],
        token_count=response["usage"]["completion_tokens"],
        model=response["model"],
        finish_reason=response.get("finish_reason", "stop"),
        latency_ms=latency_ms,
        cost_estimate=cost,
        thinking_enabled=thinking_enabled,
        metadata={"usage": response["usage"]},
    )

    # Update conversation counters (2 messages: user + assistant)
    conv_repo.increment_message_count(conversation_id, user_tokens)
    conv_repo.increment_message_count(conversation_id, response["usage"]["completion_tokens"])

    # Auto-title on first message
    if conversation.get("message_count", 0) == 0:
        thread = threading.Thread(
            target=_trigger_auto_title,
            args=(conversation_id, content),
            daemon=True,
        )
        thread.start()

    return assistant_msg


def prepare_stream(
    conversation_id: str,
    content: str,
    thinking_enabled: bool = False,
    conversation: dict | None = None,
):
    """
    Prepare streaming: persist user message, build context, get stream.
    Returns (stream, model, user_msg, conversation).
    """
    if conversation is None:
        conversation = conv_repo.get_conversation(conversation_id, user_id=None)

    system_prompt = conversation.get("system_prompt") or DEFAULT_SYSTEM_PROMPT
    if thinking_enabled:
        system_prompt += THINKING_MODE_ADDON

    model = conversation.get("model", "llama-3.1-8b-instant")

    # Persist user message
    user_tokens = count_tokens(content)
    user_msg = _persist_message(
        conversation_id=conversation_id,
        role="user",
        content=content,
        token_count=user_tokens,
        thinking_enabled=thinking_enabled,
    )

    # Build context
    history = _get_conversation_messages(conversation_id)
    context = build_context(history, system_prompt, model=model)

    # Get streaming response
    stream, used_model = llm_client.chat_completion_stream(context, model=model)

    return stream, used_model, user_msg, conversation


def persist_stream_result(
    conversation_id: str,
    content: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int = 0,
    finish_reason: str = "stop",
    thinking_enabled: bool = False,
    is_first_message: bool = False,
    first_user_content: str = "",
):
    """Persist the assistant message after streaming completes."""
    if not content:
        return

    cost = calculate_cost(model, prompt_tokens, completion_tokens)

    _persist_message(
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        token_count=completion_tokens,
        model=model,
        finish_reason=finish_reason,
        latency_ms=latency_ms,
        cost_estimate=cost,
        thinking_enabled=thinking_enabled,
        metadata={"usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}},
    )

    # Update conversation counters
    conv_repo.increment_message_count(conversation_id, completion_tokens)

    # Auto-title on first message
    if is_first_message and first_user_content:
        thread = threading.Thread(
            target=_trigger_auto_title,
            args=(conversation_id, first_user_content),
            daemon=True,
        )
        thread.start()
