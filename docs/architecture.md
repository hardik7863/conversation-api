# Architecture Decisions

## Overview

This document explains the key architectural decisions made for the AI Conversation API.

## Authentication: Custom JWT over Supabase Auth

**Decision**: Use custom JWT authentication (bcrypt + PyJWT) instead of Supabase Auth.

**Rationale**:
- Full control over token lifecycle (15-min access, 7-day refresh)
- Refresh token rotation with SHA-256 hashing
- No dependency on Supabase Auth service availability
- Custom password validation rules
- Simpler integration with the rate limiter (user_id extraction)

**Trade-offs**: We manage password hashing and token storage ourselves, but gain flexibility.

## Database Access: Service Role Key with App-Level Filtering

**Decision**: Use Supabase `service_role` key (bypasses RLS) with app-level `user_id` filtering as the primary authorization guard. RLS policies exist as defense-in-depth.

**Rationale**:
- Since we use custom JWT (not Supabase Auth), `auth.uid()` in RLS policies wouldn't work with our tokens
- Service role key gives the API full database access
- Every query explicitly filters by `user_id` to prevent cross-user data access
- RLS is enabled with permissive policies as a safety net

## LLM Integration: Groq with Model Fallback

**Decision**: Use Groq API with automatic fallback from primary model to secondary.

**Models**:
- Primary: `llama-3.1-8b-instant` (131K context window, fast, cheap)
- Fallback: `gemma2-9b-it` (8K context window)

**Fallback Logic**: On `RateLimitError` or `APIStatusError` from the primary model, automatically retry with the fallback model. Both streaming and non-streaming paths support fallback.

## Context Management: Sliding Window

**Decision**: Implement a sliding window strategy for conversation context.

**Algorithm**:
1. Always include the system prompt
2. Always include the latest user message
3. Fill remaining token budget with recent history (newest first)
4. Stop adding messages when budget is exhausted

**Rationale**: Ensures the LLM always has the system prompt and current question, while maximizing relevant context from recent conversation history.

## Streaming: SSE with Claude/OpenAI-Compatible Event Format

**Decision**: Use Server-Sent Events (SSE) with event types matching the Claude API spec.

**Event Sequence**:
```
message_start → content_block_start → content_block_delta × N →
content_block_stop → message_delta → message_stop
```

**Rationale**: Compatible event format makes it easy for frontends already built for Claude or OpenAI streaming to integrate with our API.

**Persistence**: After the stream completes, the full response is persisted to the database with token counts and cost estimates.

## Rate Limiting: Sliding Window as FastAPI Dependencies

**Decision**: Implement rate limiting as FastAPI dependencies (not middleware) with a sliding window algorithm.

**Rationale**:
- As dependencies, different rate limits can be applied per route
- Standard endpoints: 60 requests per minute
- AI/LLM endpoints: 10 requests per minute
- Sliding window provides smoother rate limiting than fixed windows
- Returns proper `429` with `Retry-After` header

**Trade-off**: In-memory storage means rate limits reset on server restart. For production, Redis would be used.

## Token Counting: tiktoken cl100k_base

**Decision**: Use OpenAI's tiktoken with `cl100k_base` encoding as an approximation for Llama 3 token counting.

**Rationale**: No official tokenizer is available for Llama 3 in Python. `cl100k_base` provides a reasonable approximation (within ~10% for most text). This is sufficient for context window management and cost estimation.

## Auto-Title Generation

**Decision**: Automatically generate conversation titles after the first message using a separate LLM call.

**Implementation**: Runs in a background thread after the first message response is delivered. Uses a low-temperature, low-token call to generate a concise title (max 6 words).

## Error Handling: Structured JSON, Never Expose Internals

**Decision**: All errors return structured JSON with error code, message, and request ID. Stack traces are never exposed.

**Format**:
```json
{
  "error": {
    "code": 401,
    "message": "Invalid authentication token",
    "request_id": "uuid"
  }
}
```

## Cost Tracking

**Decision**: Track hypothetical costs based on Groq's per-token pricing for each AI response.

**Implementation**: After each LLM call, calculate cost using the model's pricing rates and store it in the message metadata. Aggregate costs are available via the `/usage/stats` endpoint.
