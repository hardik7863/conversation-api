"""Shared test fixtures."""
import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Register and login a test user, return auth headers."""
    import uuid
    unique = uuid.uuid4().hex[:8]
    email = f"test_{unique}@example.com"
    password = "TestPass123"
    username = f"testuser_{unique}"

    # Register
    reg_response = client.post("/api/v1/auth/register", json={
        "email": email,
        "username": username,
        "password": password,
    })

    # Login
    login_response = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    tokens = login_response.json()

    return {
        "Authorization": f"Bearer {tokens['access_token']}",
        "refresh_token": tokens["refresh_token"],
        "email": email,
        "username": username,
        "user_id": reg_response.json()["user"]["id"],
    }


@pytest.fixture
def conversation_id(client, auth_headers):
    """Create a test conversation and return its ID."""
    response = client.post(
        "/api/v1/conversations",
        json={"title": "Test Conversation"},
        headers={"Authorization": auth_headers["Authorization"]},
    )
    return response.json()["id"]
