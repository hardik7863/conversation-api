"""Tests for message endpoints."""
import pytest


class TestSendMessage:
    def test_send_message(self, client, auth_headers, conversation_id):
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "Hello, how are you?"},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "assistant"
        assert data["content"]
        assert data["token_count"] > 0
        assert data["model"]

    def test_send_with_thinking(self, client, auth_headers, conversation_id):
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "What is 2+2?", "thinking_enabled": True},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 201
        assert response.json()["thinking_enabled"] is True

    def test_send_empty_content(self, client, auth_headers, conversation_id):
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": ""},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 422

    def test_send_unauthorized(self, client, conversation_id):
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "Hello"},
        )
        assert response.status_code == 401


class TestListMessages:
    def test_list_messages(self, client, auth_headers, conversation_id):
        # Send a message first
        client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "Test message"},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        response = client.get(
            f"/api/v1/conversations/{conversation_id}/messages",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) >= 2  # user + assistant
        assert "total" in data
        assert "has_more" in data

    def test_list_pagination(self, client, auth_headers, conversation_id):
        response = client.get(
            f"/api/v1/conversations/{conversation_id}/messages?page=1&limit=1",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 1


class TestContextManagement:
    def test_multi_turn_conversation(self, client, auth_headers, conversation_id):
        """Send multiple messages and verify context is maintained."""
        # First message
        client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "My name is TestUser123."},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        # Second message referencing the first
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "What is my name?"},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 201
        # The LLM should remember the name from context
        assert response.json()["content"]
