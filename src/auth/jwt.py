"""JWT token creation and verification, refresh token hashing."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from src.config.settings import settings


def create_access_token(user_id: str, email: str) -> str:
    """Create a short-lived access token (15 min default)."""
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token() -> str:
    """Generate a cryptographically secure refresh token."""
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token with SHA-256 for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def decode_access_token(token: str) -> dict:
    """Decode and verify an access token. Raises jwt exceptions on failure."""
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid token type")
    return payload


def get_refresh_token_expiry() -> datetime:
    """Get the expiry datetime for a new refresh token."""
    return datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
