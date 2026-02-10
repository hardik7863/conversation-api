"""Sliding window context management for LLM conversations."""
from src.llm.token_counter import count_tokens

# Model context windows
MODEL_CONTEXT_WINDOWS = {
    "llama-3.1-8b-instant": 131072,
    "gemma2-9b-it": 8192,
}

# Reserve tokens for the response
RESPONSE_RESERVE = 4096


def build_context(
    messages: list[dict],
    system_prompt: str,
    max_tokens: int | None = None,
    model: str = "llama-3.1-8b-instant",
) -> list[dict]:
    """
    Build a context window using sliding window strategy.

    Always keeps: system prompt + latest user message.
    Fills remaining budget with recent history (newest first).
    """
    if max_tokens is None:
        max_tokens = MODEL_CONTEXT_WINDOWS.get(model, 8192) - RESPONSE_RESERVE

    context = []

    # System prompt always included
    system_msg = {"role": "system", "content": system_prompt}
    system_tokens = count_tokens(system_prompt) + 4
    budget = max_tokens - system_tokens

    if not messages:
        return [system_msg]

    # Latest message always included
    latest = messages[-1]
    latest_tokens = count_tokens(latest.get("content", "")) + 4
    budget -= latest_tokens

    # Fill remaining budget with history (newest to oldest, excluding the latest)
    history = messages[:-1]
    included_history = []

    for msg in reversed(history):
        msg_tokens = count_tokens(msg.get("content", "")) + 4
        if budget - msg_tokens < 0:
            break
        included_history.insert(0, msg)
        budget -= msg_tokens

    # Assemble context: system → history → latest
    context = [system_msg] + included_history + [latest]
    return context
