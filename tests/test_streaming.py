"""Tests for streaming SSE endpoints."""
import json
import pytest


class TestStreamMessage:
    def test_stream_sse_events(self, client, auth_headers, conversation_id):
        """Test that streaming returns proper SSE event format."""
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/messages/stream",
            json={"content": "Say hello in one word."},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        # Parse SSE events
        events = []
        for line in response.text.split("\n"):
            if line.startswith("event: "):
                events.append(line.replace("event: ", ""))

        # Verify event sequence
        assert "message_start" in events
        assert "content_block_start" in events
        assert "content_block_delta" in events
        assert "content_block_stop" in events
        assert "message_delta" in events
        assert "message_stop" in events

    def test_stream_contains_content(self, client, auth_headers, conversation_id):
        """Verify that streamed content is non-empty."""
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/messages/stream",
            json={"content": "What is 1+1?"},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        # Extract content from content_block_delta events
        content_parts = []
        lines = response.text.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    if data.get("type") == "content_block_delta":
                        content_parts.append(data["delta"]["text"])
                except json.JSONDecodeError:
                    pass

        full_content = "".join(content_parts)
        assert len(full_content) > 0

    def test_stream_message_persisted(self, client, auth_headers, conversation_id):
        """Verify that streamed messages are persisted to the database."""
        client.post(
            f"/api/v1/conversations/{conversation_id}/messages/stream",
            json={"content": "Hello stream test"},
            headers={"Authorization": auth_headers["Authorization"]},
        )

        # Check messages were saved
        response = client.get(
            f"/api/v1/conversations/{conversation_id}/messages",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 200
        messages = response.json()["messages"]
        assert len(messages) >= 2  # user + assistant
        roles = [m["role"] for m in messages]
        assert "user" in roles
        assert "assistant" in roles

    def test_stream_unauthorized(self, client, conversation_id):
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/messages/stream",
            json={"content": "Hello"},
        )
        assert response.status_code == 401


class TestSecurityHeaders:
    def test_request_id_header(self, client):
        response = client.get("/health")
        assert "x-request-id" in response.headers

    def test_security_headers_present(self, client):
        response = client.get("/health")
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert response.headers.get("x-xss-protection") == "1; mode=block"
        assert "strict-transport-security" in response.headers


class TestHealthCheck:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_api_health(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200


class TestModelsEndpoint:
    def test_list_models(self, client):
        response = client.get("/api/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert len(data["models"]) > 0
        model = data["models"][0]
        assert "id" in model
        assert "context_window" in model
        assert "pricing" in model
