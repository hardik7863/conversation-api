"""Sliding-window rate limiter implemented as FastAPI dependencies."""
import time
from collections import defaultdict
from fastapi import HTTPException, Request

# In-memory store: user_id -> list of timestamps
_request_log: dict[str, list[float]] = defaultdict(list)


def _cleanup(timestamps: list[float], window: int) -> list[float]:
    """Remove timestamps older than the window."""
    cutoff = time.time() - window
    return [t for t in timestamps if t > cutoff]


def _check_rate_limit(user_id: str, max_requests: int, window: int = 60) -> dict:
    """Check and enforce rate limit. Returns rate-limit headers info."""
    now = time.time()
    key = f"{user_id}"
    _request_log[key] = _cleanup(_request_log[key], window)

    remaining = max_requests - len(_request_log[key])

    if remaining <= 0:
        oldest = _request_log[key][0] if _request_log[key] else now
        retry_after = int(oldest + window - now) + 1
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(oldest + window)),
            },
        )

    _request_log[key].append(now)
    reset_time = int(_request_log[key][0] + window)

    return {
        "X-RateLimit-Limit": str(max_requests),
        "X-RateLimit-Remaining": str(remaining - 1),
        "X-RateLimit-Reset": str(reset_time),
    }


async def standard_rate_limit(request: Request) -> dict:
    """60 requests per minute per user for standard endpoints."""
    from src.config.settings import settings
    user = getattr(request.state, "current_user", None)
    user_id = user["id"] if user else request.client.host if request.client else "anonymous"
    return _check_rate_limit(f"std:{user_id}", settings.rate_limit_standard_rpm)


async def ai_rate_limit(request: Request) -> dict:
    """10 requests per minute per user for AI/LLM endpoints."""
    from src.config.settings import settings
    user = getattr(request.state, "current_user", None)
    user_id = user["id"] if user else request.client.host if request.client else "anonymous"
    return _check_rate_limit(f"ai:{user_id}", settings.rate_limit_ai_rpm)
