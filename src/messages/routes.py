"""Message routes: send, stream (SSE), list, events."""
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from src.auth.dependencies import get_current_user, verify_conversation_ownership
from src.messages import service
from src.messages.schemas import MessageCreate, MessageListResponse, MessageResponse
from src.messages.streaming import format_sse_event, stream_with_persistence
from src.middleware.rate_limiter import ai_rate_limit, standard_rate_limit

router = APIRouter(prefix="/conversations/{conversation_id}/messages", tags=["Messages"])

# Separate router for events (different URL prefix)
events_router = APIRouter(prefix="/conversations/{conversation_id}", tags=["Streaming"])


@router.post("", status_code=201, response_model=MessageResponse)
async def send_message(
    conversation_id: str,
    body: MessageCreate,
    conversation: dict = Depends(verify_conversation_ownership),
    _rate=Depends(ai_rate_limit),
):
    """Send a message and get a non-streaming AI response."""
    return service.send_message(
        conversation_id=conversation_id,
        content=body.content,
        thinking_enabled=body.thinking_enabled,
        conversation=conversation,
    )


@router.post("/stream", status_code=200)
async def stream_message(
    conversation_id: str,
    body: MessageCreate,
    conversation: dict = Depends(verify_conversation_ownership),
    _rate=Depends(ai_rate_limit),
):
    """Send a message and get a streaming SSE AI response."""
    stream, model, user_msg, conv = service.prepare_stream(
        conversation_id=conversation_id,
        content=body.content,
        thinking_enabled=body.thinking_enabled,
        conversation=conversation,
    )

    is_first = conv.get("message_count", 0) == 0

    event_generator, result_container = stream_with_persistence(
        stream=stream,
        model=model,
        conversation_id=conversation_id,
    )

    def streaming_response():
        for event in event_generator():
            yield event

        # After stream completes, persist the result
        service.persist_stream_result(
            conversation_id=conversation_id,
            content=result_container["content"],
            model=result_container["model"],
            prompt_tokens=result_container["prompt_tokens"],
            completion_tokens=result_container["completion_tokens"],
            latency_ms=result_container.get("latency_ms", 0),
            finish_reason=result_container.get("finish_reason", "stop"),
            thinking_enabled=body.thinking_enabled,
            is_first_message=is_first,
            first_user_content=body.content,
        )

    return StreamingResponse(
        streaming_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("", response_model=MessageListResponse)
async def list_messages(
    conversation_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    conversation: dict = Depends(verify_conversation_ownership),
    _rate=Depends(standard_rate_limit),
):
    """List messages in a conversation with pagination."""
    return service.get_messages(
        conversation_id=conversation_id,
        page=page,
        limit=limit,
    )


@events_router.get("/events", tags=["Streaming"])
async def conversation_events(
    conversation_id: str,
    conversation: dict = Depends(verify_conversation_ownership),
    _rate=Depends(standard_rate_limit),
):
    """
    SSE stream of real-time conversation events.
    Sends the latest messages as SSE events and keeps the connection open
    for future real-time events.
    """
    from src.db.client import get_supabase_client
    from src.db.models import MESSAGES_TABLE

    def event_stream():
        # Send existing messages as SSE events for replay
        db = get_supabase_client()
        messages = (
            db.table(MESSAGES_TABLE)
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .execute()
        )

        for msg in messages.data:
            if msg["role"] == "assistant":
                # Replay assistant message as SSE events
                yield format_sse_event("message_start", {
                    "type": "message_start",
                    "message": {
                        "id": msg["id"],
                        "role": "assistant",
                        "model": msg.get("model", "unknown"),
                    },
                })
                yield format_sse_event("content_block_start", {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                })
                yield format_sse_event("content_block_delta", {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": msg["content"]},
                })
                yield format_sse_event("content_block_stop", {
                    "type": "content_block_stop",
                    "index": 0,
                })
                yield format_sse_event("message_delta", {
                    "type": "message_delta",
                    "delta": {"stop_reason": msg.get("finish_reason", "end_turn")},
                    "usage": {"output_tokens": msg.get("token_count", 0)},
                })
                yield format_sse_event("message_stop", {
                    "type": "message_stop",
                })
            else:
                # Send user/system messages as a simple event
                yield format_sse_event("message_start", {
                    "type": "message_start",
                    "message": {
                        "id": msg["id"],
                        "role": msg["role"],
                        "content": msg["content"],
                    },
                })
                yield format_sse_event("message_stop", {
                    "type": "message_stop",
                })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
