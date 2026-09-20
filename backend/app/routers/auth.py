"""
V-SHIELD Authentication & Session Management Router (SIH 2026).
Provides:
1. POST /api/v1/auth/login (and /token): Issues HMAC-SHA256 JWT access tokens.
2. GET /api/v1/auth/me: Returns current authenticated operator identity.
3. POST /api/v1/auth/session: Creates an active live analysis session token.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.core.auth import (
    TokenExpiredError,
    authenticate_user,
    create_access_token,
    verify_access_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Session Security"])


# =====================================================================
# Request & Response Schemas
# =====================================================================


class LoginRequest(BaseModel):
    username: str = Field(..., description="Operator username or email")
    password: str = Field(..., description="Operator password")


class UserProfile(BaseModel):
    user_id: str
    username: str
    name: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile


class SessionCreateResponse(BaseModel):
    session_id: str
    token: str
    user_id: str
    expires_in: int


# =====================================================================
# FastAPI Dependencies
# =====================================================================


async def get_current_user(
    authorization: Optional[str] = Header(None, description="Bearer <JWT Token>"),
) -> Dict[str, Any]:
    """
    Dependency that enforces a valid logged-in user identity from Authorization header.
    Raises HTTPException(401) on missing, invalid, or expired tokens.
    Never logs raw tokens or authorization headers.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    try:
        payload = verify_access_token(token)
        return payload
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )


# =====================================================================
# Authentication Endpoints
# =====================================================================


@router.post("/login", response_model=TokenResponse)
@router.post("/token", response_model=TokenResponse)
async def login(credentials: LoginRequest) -> TokenResponse:
    """
    Authenticates operator credentials and returns an HMAC-SHA256 JWT access token.
    Never logs passwords or issued JWT secrets.
    """
    user = authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    token = create_access_token(
        data={
            "sub": user["user_id"],
            "username": user["username"],
            "role": user["role"],
        }
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserProfile(**user),
    )


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> UserProfile:
    """Returns the authenticated operator profile."""
    return UserProfile(
        user_id=current_user.get("sub", "usr_unknown"),
        username=current_user.get("username", "unknown"),
        name=current_user.get("username", "Operator"),
        role=current_user.get("role", "operator"),
    )


@router.post("/session", response_model=SessionCreateResponse)
async def create_analysis_session(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> SessionCreateResponse:
    """Generates an authorized session token bound to the current logged-in user."""
    import time

    session_id = f"sess_{int(time.time() * 1000)}"
    expires_in = settings.SESSION_MAX_DURATION_SECONDS

    session_token = create_access_token(
        data={
            "sub": current_user.get("sub"),
            "username": current_user.get("username"),
            "role": current_user.get("role"),
            "session_id": session_id,
        }
    )

    return SessionCreateResponse(
        session_id=session_id,
        token=session_token,
        user_id=str(current_user.get("sub")),
        expires_in=expires_in,
    )
