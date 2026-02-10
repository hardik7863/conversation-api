"""Groq LLM client with model fallback support."""
import logging
from typing import AsyncGenerator

from groq import Groq, RateLimitError, APIStatusError

from src.config.settings import settings

logger = logging.getLogger(__name__)

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def chat_completion(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> dict:
    """
    Send a chat completion request with automatic fallback.
    Returns the full response dict.
    """
    client = _get_client()
    primary = model or settings.groq_primary_model
    fallback = settings.groq_fallback_model

    for attempt_model in [primary, fallback]:
        try:
            response = client.chat.completions.create(
                model=attempt_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return {
                "content": response.choices[0].message.content,
                "model": attempt_model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "finish_reason": response.choices[0].finish_reason,
            }
        except (RateLimitError, APIStatusError) as e:
            if attempt_model == fallback:
                logger.error(f"Both models failed: {e}")
                raise
            logger.warning(f"Model {attempt_model} failed ({e}), falling back to {fallback}")
            continue

    raise RuntimeError("All models failed")


def chat_completion_stream(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
):
    """
    Send a streaming chat completion request with fallback.
    Returns (stream_iterator, model_used).
    """
    client = _get_client()
    primary = model or settings.groq_primary_model
    fallback = settings.groq_fallback_model

    for attempt_model in [primary, fallback]:
        try:
            stream = client.chat.completions.create(
                model=attempt_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            return stream, attempt_model
        except (RateLimitError, APIStatusError) as e:
            if attempt_model == fallback:
                logger.error(f"Both models failed for streaming: {e}")
                raise
            logger.warning(f"Model {attempt_model} failed ({e}), falling back to {fallback}")
            continue

    raise RuntimeError("All models failed")


def generate_title(message: str) -> str:
    """Generate a short title for a conversation based on the first message."""
    from src.llm.prompts import TITLE_GENERATION_PROMPT

    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=settings.groq_primary_model,
            messages=[
                {"role": "user", "content": TITLE_GENERATION_PROMPT.format(message=message[:500])}
            ],
            temperature=0.3,
            max_tokens=30,
        )
        title = response.choices[0].message.content.strip()
        # Clean up: remove quotes, limit length
        title = title.strip('"\'').strip()
        return title[:255] if title else "New Conversation"
    except Exception as e:
        logger.warning(f"Title generation failed: {e}")
        return "New Conversation"
