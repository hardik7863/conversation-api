"""AI Conversation API — Entry point."""
import logging

from fastapi import FastAPI, Depends, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.auth.dependencies import get_current_user
from src.config.cors import CORS_CONFIG
from src.config.settings import settings
from src.middleware.error_handler import (
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from src.middleware.request_id import RequestIDMiddleware
from src.middleware.security_headers import SecurityHeadersMiddleware
from src.middleware.rate_limiter import standard_rate_limit
from src.db.client import get_supabase_client
from src.db.models import MESSAGES_TABLE
from src.llm.context import MODEL_CONTEXT_WINDOWS

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.app_debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(
    title="AI Conversation API",
    description="Production-grade REST API for managing AI conversations with streaming support.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Health", "description": "Health check endpoint"},
        {"name": "Auth", "description": "Authentication & authorization"},
        {"name": "Conversations", "description": "Conversation CRUD operations"},
        {"name": "Messages", "description": "Message sending & retrieval"},
        {"name": "Streaming", "description": "Server-Sent Events streaming"},
        {"name": "Usage", "description": "Token usage statistics"},
        {"name": "Models", "description": "Available AI models"},
    ],
)

# --- Middleware stack (order matters: outermost first) ---
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(CORSMiddleware, **CORS_CONFIG)

# --- Exception handlers ---
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# --- Routers ---
from src.auth.routes import router as auth_router
from src.conversations.routes import router as conversations_router
from src.messages.routes import router as messages_router
from src.messages.routes import events_router

app.include_router(auth_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(messages_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")


# --- Health check ---
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.app_env,
    }


@app.get("/api/v1/health", tags=["Health"])
async def api_health_check():
    """API health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.app_env,
    }


# --- Bonus Endpoints ---

@app.get("/api/v1/usage/stats", tags=["Usage"])
async def get_usage_stats(
    current_user: dict = Depends(get_current_user),
    _rate=Depends(standard_rate_limit),
):
    """Get token usage aggregation for the current user."""
    db = get_supabase_client()

    # Get all messages from user's conversations
    from src.db.models import CONVERSATIONS_TABLE
    conversations = (
        db.table(CONVERSATIONS_TABLE)
        .select("id, total_tokens, message_count, model")
        .eq("user_id", current_user["id"])
        .execute()
    )

    total_conversations = len(conversations.data)
    total_messages = sum(c.get("message_count", 0) for c in conversations.data)
    total_tokens = sum(c.get("total_tokens", 0) for c in conversations.data)

    # Get cost estimates from messages
    conversation_ids = [c["id"] for c in conversations.data]
    total_cost = 0.0
    if conversation_ids:
        for conv_id in conversation_ids:
            msgs = (
                db.table(MESSAGES_TABLE)
                .select("cost_estimate")
                .eq("conversation_id", conv_id)
                .eq("role", "assistant")
                .execute()
            )
            total_cost += sum(float(m.get("cost_estimate", 0)) for m in msgs.data)

    # Model usage breakdown
    model_usage = {}
    for c in conversations.data:
        model = c.get("model", "unknown")
        if model not in model_usage:
            model_usage[model] = {"conversations": 0, "tokens": 0}
        model_usage[model]["conversations"] += 1
        model_usage[model]["tokens"] += c.get("total_tokens", 0)

    return {
        "user_id": current_user["id"],
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "total_tokens": total_tokens,
        "total_cost_estimate": round(total_cost, 8),
        "model_usage": model_usage,
    }


@app.get("/api/v1/models", tags=["Models"])
async def list_models(_rate=Depends(standard_rate_limit)):
    """List available AI models with context windows and pricing."""
    from src.utils.cost_tracker import MODEL_PRICING

    models = []
    for model_id, context_window in MODEL_CONTEXT_WINDOWS.items():
        pricing = MODEL_PRICING.get(model_id, {})
        models.append({
            "id": model_id,
            "name": model_id,
            "context_window": context_window,
            "pricing": {
                "input_per_million_tokens": pricing.get("input", 0),
                "output_per_million_tokens": pricing.get("output", 0),
            },
            "is_primary": model_id == settings.groq_primary_model,
        })

    return {"models": models}
