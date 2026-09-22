"""
V-SHIELD Authentication & Session Management Router (SIH 2026).
Provides:
1. POST /api/v1/auth/login (and /token): Issues HMAC-SHA256 JWT access tokens and sets secure session cookie.
2. GET /api/v1/auth/me: Returns current authenticated operator identity (via Bearer header or cookie).
3. POST /api/v1/auth/session: Creates an active live analysis session token.
4. POST /api/v1/auth/logout: Clears active session cookies.
5. GET /api/v1/auth/google/login: Initiates real Google OAuth 2.0 OpenID Connect authorization.
6. GET /api/v1/auth/google/callback: Handles Google OAuth callback, verifies identity, provisions user, and creates session.
"""

import logging
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.core.auth import (
    USERS_DB,
    TokenExpiredError,
    authenticate_user,
    create_access_token,
    create_oauth_state,
    find_or_create_google_user,
    verify_access_token,
    verify_oauth_state,
)

logger = logging.getLogger("vshield.auth")

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
    picture: Optional[str] = None


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
# Email / Password Authentication Endpoints
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
    username = current_user.get("username", "unknown")
    user_record = USERS_DB.get(username, {})

    name = user_record.get("name") or current_user.get("name") or username
    picture = user_record.get("picture")

    return UserProfile(
        user_id=current_user.get("sub", "usr_unknown"),
        username=username,
        name=name,
        role=current_user.get("role", "operator"),
        picture=picture,
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


@router.post("/logout")
async def logout(response: Response) -> Dict[str, str]:
    """Clears the V-SHIELD authentication session cookies."""
    response.delete_cookie(key="vshield_token", path="/")
    response.delete_cookie(key="access_token", path="/")
    return {"status": "success", "message": "logged out"}


def _set_auth_cookie(response: Response, token: str, max_age: int) -> None:
    """Sets a secure, HttpOnly session cookie on the outgoing response."""
    is_prod = settings.ENVIRONMENT.lower() in ("production", "prod")
    response.set_cookie(
        key="vshield_token",
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=is_prod,
        path="/",
    )


# =====================================================================
# Google OAuth 2.0 / OpenID Connect Endpoints
# =====================================================================


@router.get("/google/login")
async def google_login(
    accept: Optional[str] = Header(None),
) -> Any:
    """
    Initiates Google OAuth 2.0 OpenID Connect authorization code flow.
    Redirects user to Google OAuth consent screen with cryptographic CSRF state.
    """
    if not settings.GOOGLE_CLIENT_ID:
        logger.warning("Google login requested but GOOGLE_CLIENT_ID is not configured.")
        frontend_login_url = (
            f"{settings.FRONTEND_URL}/login"
            f"?error={quote('google_not_configured')}"
            f"&message={quote('Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.')}"
        )
        return RedirectResponse(
            url=frontend_login_url,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    state = create_oauth_state()

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    return RedirectResponse(
        url=google_auth_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get("/google/callback")
async def google_callback(
    code: Optional[str] = Query(None, description="Google OAuth authorization code"),
    state: Optional[str] = Query(None, description="CSRF state verification parameter"),
    error: Optional[str] = Query(None, description="Google OAuth error response"),
) -> RedirectResponse:
    """
    Handles the Google OAuth 2.0 authorization code callback.
    1. Validates CSRF state.
    2. Exchanges code for tokens with Google.
    3. Verifies ID token with Google's official tokeninfo endpoint.
    4. Finds or provisions local user.
    5. Issues V-SHIELD session token and redirects to frontend dashboard.
    """
    # 1. Handle error or user cancellation from Google
    if error:
        logger.info("Google OAuth callback returned error: %s", error)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={quote(error)}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    # 2. Check required parameters
    if not code or not state:
        logger.warning("Google OAuth callback missing code or state parameter.")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={quote('missing_oauth_parameters')}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    # 3. Verify cryptographic CSRF state
    if not verify_oauth_state(state):
        logger.warning("Google OAuth callback failed CSRF state validation.")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={quote('invalid_oauth_state')}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    # 4. Check backend configuration
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        logger.error("Google OAuth callback invoked without server client credentials configured.")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={quote('server_oauth_unconfigured')}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    # 5. Exchange code for Google tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            token_res = await http_client.post(token_url, data=token_data)
            if token_res.status_code != 200:
                logger.error(
                    "Failed to exchange Google OAuth code. Status: %d", token_res.status_code
                )
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/login?error={quote('token_exchange_failed')}",
                    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                )

            token_payload = token_res.json()
            id_token = token_payload.get("id_token")
            if not id_token:
                logger.error("Google token response did not contain id_token.")
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/login?error={quote('missing_id_token')}",
                    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                )

            # 6. Verify Google identity token using Google's official tokeninfo API
            tokeninfo_url = "https://oauth2.googleapis.com/tokeninfo"
            verify_res = await http_client.get(tokeninfo_url, params={"id_token": id_token})
            if verify_res.status_code != 200:
                logger.error(
                    "Google token verification rejected by Google tokeninfo. Status: %d",
                    verify_res.status_code,
                )
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/login?error={quote('invalid_google_identity')}",
                    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                )

            google_info = verify_res.json()

    except Exception as exc:
        logger.error("Exception during Google OAuth verification: %s", exc)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={quote('oauth_network_failure')}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    # 7. Validate essential claims
    aud = google_info.get("aud")
    if aud != settings.GOOGLE_CLIENT_ID:
        logger.error(
            "Token audience mismatch. Token aud=%s, configured=%s", aud, settings.GOOGLE_CLIENT_ID
        )
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={quote('invalid_token_audience')}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    iss = google_info.get("iss")
    if iss not in ("https://accounts.google.com", "accounts.google.com"):
        logger.error("Token issuer invalid: %s", iss)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={quote('invalid_token_issuer')}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    email = google_info.get("email")
    email_verified = google_info.get("email_verified")
    if not email or str(email_verified).lower() != "true":
        logger.warning("Unverified email in Google ID token.")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={quote('unverified_google_email')}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    google_sub = google_info.get("sub", "")
    name = google_info.get("name")
    picture = google_info.get("picture")

    # 8. Find or provision local user
    user = find_or_create_google_user(
        google_sub=google_sub,
        email=email,
        name=name,
        picture=picture,
    )

    # 9. Issue standard V-SHIELD access token
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    token = create_access_token(
        data={
            "sub": user["user_id"],
            "username": user["username"],
            "role": user["role"],
        }
    )

    # 10. Redirect to dashboard with token and set HttpOnly cookie
    redirect_url = f"{settings.FRONTEND_URL}/?auth_token={token}"
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    _set_auth_cookie(response, token, expires_in)

    return response
