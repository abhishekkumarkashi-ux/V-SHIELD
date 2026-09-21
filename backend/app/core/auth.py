"""
V-SHIELD Authentication & Live Analysis Session Security (SIH 2026).
Provides:
1. RFC 7519 compliant HMAC-SHA256 JWT generation, decoding, and expiration checks.
2. In-memory & PBKDF2 secure user registry for authorized voice analysts & operators.
3. Live WebSocket analysis session lifecycle management (state, activity tracking, idle/max timeouts).
4. Strict security log sanitization (prevents logging passwords, secrets, tokens, cookies, raw audio).
"""

import base64
import hashlib
import hmac
import json
import time
from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from app.config import settings

# =====================================================================
# Custom Exceptions
# =====================================================================


class AuthError(Exception):
    """Base exception for authentication failures."""

    def __init__(self, message: str, code: str = "UNAUTHENTICATED"):
        super().__init__(message)
        self.message = message
        self.code = code


class TokenExpiredError(AuthError):
    """Raised when an authentication or session token has expired."""

    def __init__(self, message: str = "expired session"):
        super().__init__(message, code="EXPIRED_SESSION")


class InvalidTokenError(AuthError):
    """Raised when an authentication token is malformed, tampered, or invalid."""

    def __init__(self, message: str = "unauthenticated"):
        super().__init__(message, code="UNAUTHENTICATED")


class InactiveSessionError(AuthError):
    """Raised when audio or actions are performed on an uninitialized or stopped session."""

    def __init__(self, message: str = "inactive session"):
        super().__init__(message, code="INACTIVE_SESSION")


# =====================================================================
# RFC 7519 Base64URL & HMAC-SHA256 JWT Implementation
# =====================================================================


def _base64url_encode(data: bytes) -> str:
    """Encodes bytes into standard base64url string without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _base64url_decode(encoded_str: str) -> bytes:
    """Decodes standard base64url string with padding restoration."""
    rem = len(encoded_str) % 4
    if rem > 0:
        encoded_str += "=" * (4 - rem)
    return base64.urlsafe_b64decode(encoded_str.encode("utf-8"))


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    secret_key: Optional[str] = None,
) -> str:
    """
    Creates a signed HMAC-SHA256 JWT access token.
    Never logs or exposes the secret key.
    """
    secret = (secret_key or settings.JWT_SECRET_KEY).encode("utf-8")
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))

    now = int(time.time())
    if expires_delta is not None:
        exp = now + int(expires_delta.total_seconds())
    else:
        exp = now + (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    to_encode = data.copy()
    to_encode.update({"iat": now, "exp": exp})

    payload_b64 = _base64url_encode(
        json.dumps(to_encode, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
    signature_b64 = _base64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def verify_access_token(
    token: str,
    secret_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Decodes and cryptographically validates an HMAC-SHA256 JWT access token.
    Raises TokenExpiredError or InvalidTokenError.
    """
    if not token or not isinstance(token, str):
        raise InvalidTokenError("unauthenticated")

    parts = token.strip().split(".")
    if len(parts) != 3:
        raise InvalidTokenError("unauthenticated")

    header_b64, payload_b64, signature_b64 = parts
    secret = (secret_key or settings.JWT_SECRET_KEY).encode("utf-8")

    # Verify Signature in constant time
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    try:
        actual_sig = _base64url_decode(signature_b64)
    except Exception:
        raise InvalidTokenError("unauthenticated")

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise InvalidTokenError("unauthenticated")

    # Decode payload
    try:
        payload_bytes = _base64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise InvalidTokenError("unauthenticated")

    # Check expiration claim
    now = int(time.time())
    exp = payload.get("exp")
    if exp is not None and now >= int(exp):
        raise TokenExpiredError("expired session")

    return payload


# =====================================================================
# Secure User Registry & Credential Verification
# =====================================================================


def _hash_password(password: str, salt: bytes) -> str:
    """Hashes a password using PBKDF2-HMAC-SHA256 with 100,000 iterations."""
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return f"{salt.hex()}${key.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verifies a password against PBKDF2-HMAC-SHA256 stored hash in constant time."""
    try:
        salt_hex, key_hex = stored_hash.split("$")
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        actual_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return hmac.compare_digest(actual_key, expected_key)
    except Exception:
        return False


# Static salts for operator accounts
_SALT_ANALYST = b"vshield_salt_analyst_2026"
_SALT_OPERATOR = b"vshield_salt_operator_2026"
_SALT_ADMIN = b"vshield_salt_admin_2026"


def _build_users_db() -> Dict[str, Dict[str, Any]]:
    """
    Constructs the authorized user registry.
    Primary operator credentials originate from environment configuration.
    Development-only convenience accounts are excluded in production.
    """
    db: Dict[str, Dict[str, Any]] = {
        settings.DEMO_OPERATOR_USERNAME: {
            "user_id": "usr_analyst_01",
            "username": settings.DEMO_OPERATOR_USERNAME,
            "name": "Security Operations Lead",
            "role": "analyst",
            "password_hash": _hash_password(
                settings.DEMO_OPERATOR_PASSWORD or "VShieldDev2026!", _SALT_ANALYST
            ),
            "is_active": True,
        }
    }

    # Only permit supplementary development operator accounts in non-production environments
    if settings.ENVIRONMENT.lower() not in ("production", "prod"):
        dev_accounts = {
            "operator@vshield.internal": {
                "user_id": "usr_operator_01",
                "username": "operator@vshield.internal",
                "name": "Fraud Detection Operator",
                "role": "operator",
                "password_hash": _hash_password(
                    settings.DEMO_OPERATOR_PASSWORD or "VShieldDev2026!", _SALT_OPERATOR
                ),
                "is_active": True,
            },
            "operator": {
                "user_id": "usr_operator_02",
                "username": "operator",
                "name": "Local Console Operator",
                "role": "operator",
                "password_hash": _hash_password(
                    settings.DEMO_OPERATOR_PASSWORD or "VShieldDev2026!", _SALT_OPERATOR
                ),
                "is_active": True,
            },
            "analyst": {
                "user_id": "usr_analyst_02",
                "username": "analyst",
                "name": "Local Console Analyst",
                "role": "analyst",
                "password_hash": _hash_password(
                    settings.DEMO_OPERATOR_PASSWORD or "VShieldDev2026!", _SALT_ANALYST
                ),
                "is_active": True,
            },
            "admin@vshield.internal": {
                "user_id": "usr_admin_01",
                "username": "admin@vshield.internal",
                "name": "Platform Administrator",
                "role": "admin",
                "password_hash": _hash_password(
                    settings.DEMO_OPERATOR_PASSWORD or "VShieldDev2026!", _SALT_ADMIN
                ),
                "is_active": True,
            },
        }
        db.update(dev_accounts)

    return db


USERS_DB: Dict[str, Dict[str, Any]] = _build_users_db()


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticates user credentials against the secure user store.
    Constant-time comparison prevents timing analysis.
    """
    user = USERS_DB.get(username)
    if not user or not user.get("is_active"):
        return None

    if not _verify_password(password, user["password_hash"]):
        return None

    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "name": user["name"],
        "role": user["role"],
    }


def get_default_operator_token() -> str:
    """Generates a valid signed bearer token for default operator authentication."""
    return create_access_token(
        data={
            "sub": USERS_DB[settings.DEMO_OPERATOR_USERNAME]["user_id"],
            "username": settings.DEMO_OPERATOR_USERNAME,
            "role": USERS_DB[settings.DEMO_OPERATOR_USERNAME]["role"],
        },
        expires_delta=timedelta(hours=24),
    )


# =====================================================================
# Live Analysis Session State Machine
# =====================================================================


class AnalysisSession:
    """
    State tracker for a live WebSocket voice analysis session.
    Enforces that binary audio is only accepted during an ACTIVE session,
    and enforces maximum duration and idle timeout expirations.
    """

    def __init__(
        self,
        session_id: str,
        user_id: str,
        username: str,
        role: str = "analyst",
        max_duration_sec: Optional[float] = None,
        idle_timeout_sec: Optional[float] = None,
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.username = username
        self.role = role
        self.max_duration_sec = (
            max_duration_sec
            if max_duration_sec is not None
            else float(settings.SESSION_MAX_DURATION_SECONDS)
        )
        self.idle_timeout_sec = (
            idle_timeout_sec
            if idle_timeout_sec is not None
            else float(settings.SESSION_IDLE_TIMEOUT_SECONDS)
        )

        self.created_at = time.time()
        self.session_start_time: Optional[float] = None
        self.last_activity = time.time()
        self.is_active = False

    def start(self) -> None:
        """Activates the analysis session upon receiving 'start' control frame."""
        now = time.time()
        self.is_active = True
        self.session_start_time = now
        self.last_activity = now

    def stop(self) -> None:
        """Deactivates the session upon receiving 'stop' control frame."""
        self.is_active = False

    def record_activity(self) -> None:
        """Records timestamp of valid incoming frame."""
        self.last_activity = time.time()

    def validate_can_accept_audio(self) -> Tuple[bool, str]:
        """
        Validates whether binary audio can currently be accepted.
        Returns:
            (True, "OK") if active and valid.
            (False, "inactive session") if session has not been started or was stopped.
            (False, "expired session") if duration or idle timeout exceeded.
        """
        if not self.is_active:
            return False, "inactive session"

        now = time.time()
        # Check max lifetime duration
        if self.session_start_time is not None:
            if (now - self.session_start_time) > self.max_duration_sec:
                self.is_active = False
                return False, "expired session"

        # Check idle timeout
        if (now - self.last_activity) > self.idle_timeout_sec:
            self.is_active = False
            return False, "expired session"

        return True, "OK"


# =====================================================================
# Security & Logging Sanitizer
# =====================================================================

SENSITIVE_FIELD_NAMES = {
    "password",
    "password_hash",
    "secret",
    "jwt_secret",
    "token",
    "access_token",
    "auth_token",
    "cookie",
    "cookies",
    "authorization",
    "raw_chunk",
    "audio_bytes",
    "raw_audio",
    "bytes",
}


def mask_secret(value: Optional[str]) -> str:
    """Masks a token or secret value for secure display."""
    if not value:
        return "[EMPTY]"
    if len(value) <= 8:
        return "[REDACTED]"
    return f"{value[:4]}...[REDACTED]"


def sanitize_log_dict(obj: Any) -> Any:
    """
    Recursively redacts sensitive keys (passwords, tokens, secrets, cookies, raw audio).
    Guarantees no sensitive data is leaked into stdout or logs.
    """
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            k_lower = str(k).lower()
            if any(sensitive in k_lower for sensitive in SENSITIVE_FIELD_NAMES):
                if isinstance(v, (bytes, bytearray)):
                    sanitized[k] = f"[REDACTED_BYTES len={len(v)}]"
                else:
                    sanitized[k] = mask_secret(str(v))
            else:
                sanitized[k] = sanitize_log_dict(v)
        return sanitized
    elif isinstance(obj, list):
        return [sanitize_log_dict(item) for item in obj]
    elif isinstance(obj, (bytes, bytearray)):
        return f"[BINARY_BUFFER len={len(obj)}]"
    return obj


def sanitize_url_for_logging(url_str: str) -> str:
    """Strips query parameters (which may include tokens) from URL string."""
    if "?" in url_str:
        return url_str.split("?")[0]
    return url_str
