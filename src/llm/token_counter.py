"""Token counting using tiktoken cl100k_base as approximate for Llama 3."""
import tiktoken

_encoding = None


def _get_encoding():
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding("cl100k_base")
    return _encoding


def count_tokens(text: str) -> int:
    """Count tokens in a text string."""
    if not text:
        return 0
    return len(_get_encoding().encode(text))


def count_message_tokens(messages: list[dict]) -> int:
    """Count total tokens across a list of messages."""
    total = 0
    for msg in messages:
        # Per-message overhead (role, formatting)
        total += 4
        total += count_tokens(msg.get("content", ""))
    total += 2  # End-of-sequence overhead
    return total
