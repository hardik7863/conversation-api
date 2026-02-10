"""Auth routes: register, login, refresh, logout."""
import re
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.auth.dependencies import get_current_user
from src.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_refresh_token_expiry,
    hash_refresh_token,
)
from src.db.client import get_supabase_client
from src.db.models import REFRESH_TOKENS_TABLE, USERS_TABLE
from src.middleware.rate_limiter import standard_rate_limit

router = APIRouter(prefix="/auth", tags=["Auth"])


# --- Schemas ---

class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=255)
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v.strip()):
            raise ValueError("Invalid email format")
        return v.strip().lower()

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    created_at: str


# --- Routes ---

@router.post("/register", status_code=201, response_model=dict)
async def register(body: RegisterRequest, _rate=Depends(standard_rate_limit)):
    """Register a new user."""
    db = get_supabase_client()

    # Check for existing email
    existing = db.table(USERS_TABLE).select("id").eq("email", body.email).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Check for existing username
    existing = db.table(USERS_TABLE).select("id").eq("username", body.username).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Username already taken")

    # Hash password
    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()

    # Create user
    result = db.table(USERS_TABLE).insert({
        "email": body.email,
        "username": body.username,
        "password_hash": password_hash,
    }).execute()

    user = result.data[0]
    return {
        "message": "User registered successfully",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "created_at": user["created_at"],
        },
    }


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, _rate=Depends(standard_rate_limit)):
    """Login and receive access + refresh tokens."""
    db = get_supabase_client()

    result = db.table(USERS_TABLE).select("*").eq("email", body.email).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = result.data[0]

    if not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Account is deactivated")

    if not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Generate tokens
    access_token = create_access_token(user["id"], user["email"])
    refresh_token = create_refresh_token()

    # Store hashed refresh token
    db.table(REFRESH_TOKENS_TABLE).insert({
        "user_id": user["id"],
        "token_hash": hash_refresh_token(refresh_token),
        "expires_at": get_refresh_token_expiry().isoformat(),
    }).execute()

    from src.config.settings import settings
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, _rate=Depends(standard_rate_limit)):
    """Rotate refresh token and issue new access + refresh tokens."""
    db = get_supabase_client()
    token_hash = hash_refresh_token(body.refresh_token)

    # Find the refresh token
    result = (
        db.table(REFRESH_TOKENS_TABLE)
        .select("*")
        .eq("token_hash", token_hash)
        .eq("is_revoked", False)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid or revoked refresh token")

    stored_token = result.data[0]

    # Check expiry
    expires_at = datetime.fromisoformat(stored_token["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.now(timezone.utc):
        # Revoke expired token
        db.table(REFRESH_TOKENS_TABLE).update({"is_revoked": True}).eq("id", stored_token["id"]).execute()
        raise HTTPException(status_code=401, detail="Refresh token has expired")

    # Revoke old refresh token (rotation)
    db.table(REFRESH_TOKENS_TABLE).update({"is_revoked": True}).eq("id", stored_token["id"]).execute()

    # Get user
    user_result = db.table(USERS_TABLE).select("*").eq("id", stored_token["user_id"]).eq("is_active", True).execute()
    if not user_result.data:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    user = user_result.data[0]

    # Issue new tokens
    access_token = create_access_token(user["id"], user["email"])
    new_refresh_token = create_refresh_token()

    db.table(REFRESH_TOKENS_TABLE).insert({
        "user_id": user["id"],
        "token_hash": hash_refresh_token(new_refresh_token),
        "expires_at": get_refresh_token_expiry().isoformat(),
    }).execute()

    from src.config.settings import settings
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/logout", status_code=204)
async def logout(
    body: RefreshRequest,
    current_user: dict = Depends(get_current_user),
    _rate=Depends(standard_rate_limit),
):
    """Revoke the provided refresh token."""
    db = get_supabase_client()
    token_hash = hash_refresh_token(body.refresh_token)

    # Revoke the token if it belongs to this user
    db.table(REFRESH_TOKENS_TABLE).update({"is_revoked": True}).eq(
        "token_hash", token_hash
    ).eq("user_id", current_user["id"]).execute()

    return None
