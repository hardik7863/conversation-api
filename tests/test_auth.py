"""Tests for auth endpoints."""
import uuid
import pytest


class TestRegistration:
    def test_register_success(self, client):
        unique = uuid.uuid4().hex[:8]
        response = client.post("/api/v1/auth/register", json={
            "email": f"reg_{unique}@example.com",
            "username": f"reguser_{unique}",
            "password": "ValidPass1",
        })
        assert response.status_code == 201
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == f"reg_{unique}@example.com"

    def test_register_duplicate_email(self, client):
        unique = uuid.uuid4().hex[:8]
        payload = {
            "email": f"dup_{unique}@example.com",
            "username": f"dupuser_{unique}",
            "password": "ValidPass1",
        }
        client.post("/api/v1/auth/register", json=payload)
        payload["username"] = f"other_{unique}"
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 409

    def test_register_weak_password(self, client):
        response = client.post("/api/v1/auth/register", json={
            "email": "weak@example.com",
            "username": "weakuser",
            "password": "short",
        })
        assert response.status_code == 422

    def test_register_invalid_email(self, client):
        response = client.post("/api/v1/auth/register", json={
            "email": "notanemail",
            "username": "validuser",
            "password": "ValidPass1",
        })
        assert response.status_code == 422


class TestLogin:
    def test_login_success(self, client, auth_headers):
        """auth_headers fixture already logs in — verify tokens returned."""
        assert "Authorization" in auth_headers
        assert auth_headers["refresh_token"]

    def test_login_wrong_password(self, client, auth_headers):
        response = client.post("/api/v1/auth/login", json={
            "email": auth_headers["email"],
            "password": "WrongPass1",
        })
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        response = client.post("/api/v1/auth/login", json={
            "email": "noexist@example.com",
            "password": "ValidPass1",
        })
        assert response.status_code == 401


class TestRefreshToken:
    def test_refresh_rotation(self, client, auth_headers):
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": auth_headers["refresh_token"],
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # Old refresh token should now be revoked
        response2 = client.post("/api/v1/auth/refresh", json={
            "refresh_token": auth_headers["refresh_token"],
        })
        assert response2.status_code == 401

    def test_refresh_invalid_token(self, client):
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid_token_value",
        })
        assert response.status_code == 401


class TestLogout:
    def test_logout_success(self, client, auth_headers):
        response = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": auth_headers["refresh_token"]},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 204


class TestExpiredToken:
    def test_invalid_token(self, client):
        response = client.get(
            "/api/v1/conversations",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401

    def test_missing_token(self, client):
        response = client.get("/api/v1/conversations")
        assert response.status_code == 401
