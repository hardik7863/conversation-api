"""Tests for conversation CRUD endpoints."""
import uuid
import pytest


class TestCreateConversation:
    def test_create_default(self, client, auth_headers):
        response = client.post(
            "/api/v1/conversations",
            json={},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Conversation"
        assert data["model"] == "llama-3.1-8b-instant"
        assert data["is_archived"] is False

    def test_create_with_title(self, client, auth_headers):
        response = client.post(
            "/api/v1/conversations",
            json={"title": "My Chat", "model": "gemma2-9b-it"},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 201
        assert response.json()["title"] == "My Chat"
        assert response.json()["model"] == "gemma2-9b-it"

    def test_create_unauthorized(self, client):
        response = client.post("/api/v1/conversations", json={})
        assert response.status_code == 401


class TestListConversations:
    def test_list_paginated(self, client, auth_headers):
        # Create a few conversations
        for i in range(3):
            client.post(
                "/api/v1/conversations",
                json={"title": f"Conv {i}"},
                headers={"Authorization": auth_headers["Authorization"]},
            )
        response = client.get(
            "/api/v1/conversations?page=1&limit=2",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) <= 2
        assert "total" in data
        assert "has_more" in data

    def test_list_excludes_archived(self, client, auth_headers):
        # Create and archive a conversation
        resp = client.post(
            "/api/v1/conversations",
            json={"title": "Archived"},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        conv_id = resp.json()["id"]
        client.patch(
            f"/api/v1/conversations/{conv_id}",
            json={"is_archived": True},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        # List without archived
        response = client.get(
            "/api/v1/conversations",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        ids = [c["id"] for c in response.json()["conversations"]]
        assert conv_id not in ids

        # List with archived
        response = client.get(
            "/api/v1/conversations?include_archived=true",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        ids = [c["id"] for c in response.json()["conversations"]]
        assert conv_id in ids


class TestGetConversation:
    def test_get_own(self, client, auth_headers, conversation_id):
        response = client.get(
            f"/api/v1/conversations/{conversation_id}",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 200
        assert response.json()["id"] == conversation_id

    def test_get_nonexistent(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"/api/v1/conversations/{fake_id}",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 404

    def test_get_other_users_conversation(self, client, auth_headers, conversation_id):
        """Create a second user and try to access first user's conversation."""
        unique = uuid.uuid4().hex[:8]
        client.post("/api/v1/auth/register", json={
            "email": f"other_{unique}@example.com",
            "username": f"other_{unique}",
            "password": "OtherPass1",
        })
        login_resp = client.post("/api/v1/auth/login", json={
            "email": f"other_{unique}@example.com",
            "password": "OtherPass1",
        })
        other_token = login_resp.json()["access_token"]

        response = client.get(
            f"/api/v1/conversations/{conversation_id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert response.status_code in [403, 404]


class TestUpdateConversation:
    def test_update_title(self, client, auth_headers, conversation_id):
        response = client.patch(
            f"/api/v1/conversations/{conversation_id}",
            json={"title": "Updated Title"},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated Title"

    def test_archive(self, client, auth_headers, conversation_id):
        response = client.patch(
            f"/api/v1/conversations/{conversation_id}",
            json={"is_archived": True},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 200
        assert response.json()["is_archived"] is True


class TestDeleteConversation:
    def test_delete_own(self, client, auth_headers, conversation_id):
        response = client.delete(
            f"/api/v1/conversations/{conversation_id}",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 204

        # Verify it's gone
        response = client.get(
            f"/api/v1/conversations/{conversation_id}",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 404
