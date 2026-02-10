"""SSE event formatter and async generator matching Claude/OpenAI spec."""
import json
import logging
import time
import uuid

logger = logging.getLogger(__name__)


def format_sse_event(event_type: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def generate_sse_stream(
    stream,
    model: str,
    conversation_id: str,
    message_id: str,
):
    """
    Generator that yields SSE events from a Groq stream.
    Event format matches Claude/OpenAI spec:
      message_start → content_block_start → content_block_delta × N →
      content_block_stop → message_delta → message_stop
    """
    full_content = ""
    prompt_tokens = 0
    completion_tokens = 0

    # message_start
    yield format_sse_event("message_start", {
        "type": "message_start",
        "message": {
            "id": message_id,
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [],
        },
    })

    # content_block_start
    yield format_sse_event("content_block_start", {
        "type": "content_block_start",
        "index": 0,
        "content_block": {
            "type": "text",
            "text": "",
        },
    })

    try:
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                full_content += text

                # content_block_delta
                yield format_sse_event("content_block_delta", {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {
                        "type": "text_delta",
                        "text": text,
                    },
                })

            # Capture usage from the final chunk
            if hasattr(chunk, "x_groq") and chunk.x_groq and hasattr(chunk.x_groq, "usage"):
                usage = chunk.x_groq.usage
                prompt_tokens = usage.prompt_tokens
                completion_tokens = usage.completion_tokens

    except Exception as e:
        logger.error(f"Stream error: {e}")
        yield format_sse_event("error", {
            "type": "error",
            "error": {
                "type": "stream_error",
                "message": "An error occurred during streaming",
            },
        })
        return full_content, 0, 0

    # content_block_stop
    yield format_sse_event("content_block_stop", {
        "type": "content_block_stop",
        "index": 0,
    })

    # message_delta
    yield format_sse_event("message_delta", {
        "type": "message_delta",
        "delta": {
            "stop_reason": "end_turn",
        },
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    })

    # message_stop
    yield format_sse_event("message_stop", {
        "type": "message_stop",
    })


def stream_with_persistence(
    stream,
    model: str,
    conversation_id: str,
):
    """
    Wrapper that streams SSE events and collects the full response
    for persistence after stream completes.
    Returns a generator and a mutable container for the result.
    """
    message_id = str(uuid.uuid4())
    result_container = {
        "content": "",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "model": model,
        "message_id": message_id,
        "finish_reason": "stop",
        "latency_ms": 0,
    }

    def event_generator():
        full_content = ""
        prompt_tokens = 0
        completion_tokens = 0
        start_time = time.monotonic()

        # message_start
        yield format_sse_event("message_start", {
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [],
            },
        })

        # content_block_start
        yield format_sse_event("content_block_start", {
            "type": "content_block_start",
            "index": 0,
            "content_block": {
                "type": "text",
                "text": "",
            },
        })

        try:
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_content += text

                    yield format_sse_event("content_block_delta", {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {
                            "type": "text_delta",
                            "text": text,
                        },
                    })

                # Extract usage from the final chunk (Groq puts it in x_groq or usage)
                if hasattr(chunk, "x_groq") and chunk.x_groq:
                    usage = getattr(chunk.x_groq, "usage", None)
                    if usage:
                        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
                if hasattr(chunk, "usage") and chunk.usage:
                    prompt_tokens = getattr(chunk.usage, "prompt_tokens", 0) or 0
                    completion_tokens = getattr(chunk.usage, "completion_tokens", 0) or 0

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield format_sse_event("error", {
                "type": "error",
                "error": {
                    "type": "stream_error",
                    "message": "An error occurred during streaming",
                },
            })
            result_container["content"] = full_content
            result_container["finish_reason"] = "error"
            result_container["latency_ms"] = int((time.monotonic() - start_time) * 1000)
            return

        latency_ms = int((time.monotonic() - start_time) * 1000)

        # content_block_stop
        yield format_sse_event("content_block_stop", {
            "type": "content_block_stop",
            "index": 0,
        })

        # message_delta
        yield format_sse_event("message_delta", {
            "type": "message_delta",
            "delta": {
                "stop_reason": "end_turn",
            },
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        })

        # message_stop
        yield format_sse_event("message_stop", {
            "type": "message_stop",
        })

        # Store results for persistence
        result_container["content"] = full_content
        result_container["prompt_tokens"] = prompt_tokens
        result_container["completion_tokens"] = completion_tokens
        result_container["latency_ms"] = latency_ms

    return event_generator, result_container
