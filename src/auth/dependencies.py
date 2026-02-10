"""Auth dependencies for FastAPI route injection."""
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt as pyjwt

from src.auth.jwt import decode_access_token
from src.db.client import get_supabase_client
from src.db.models import USERS_TABLE, CONVERSATIONS_TABLE

security = HTTPBearer()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Decode Bearer token and return user dict. Sets request.state.current_user."""
    try:
        payload = decode_access_token(credentials.credentials)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    db = get_supabase_client()
    result = db.table(USERS_TABLE).select("*").eq("id", user_id).eq("is_active", True).execute()

    if not result.data:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    user = result.data[0]
    request.state.current_user = user
    return user


async def verify_conversation_ownership(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Verify that the current user owns the specified conversation."""
    db = get_supabase_client()
    result = (
        db.table(CONVERSATIONS_TABLE)
        .select("*")
        .eq("id", conversation_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = result.data[0]
    if conversation["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return conversation
