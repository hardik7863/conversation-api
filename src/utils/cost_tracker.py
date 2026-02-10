"""Hypothetical cost calculation based on Groq pricing."""
import logging

logger = logging.getLogger(__name__)

# Groq pricing per million tokens (approximate)
MODEL_PRICING = {
    "llama-3.1-8b-instant": {
        "input": 0.05,   # $0.05 per 1M input tokens
        "output": 0.08,  # $0.08 per 1M output tokens
    },
    "gemma2-9b-it": {
        "input": 0.20,
        "output": 0.20,
    },
}


def calculate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Calculate hypothetical cost for a request."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["llama-3.1-8b-instant"])
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]
    total = input_cost + output_cost
    logger.debug(f"Cost estimate for {model}: ${total:.8f} ({prompt_tokens} in, {completion_tokens} out)")
    return total
