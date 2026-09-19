"""
V-SHIELD MFA Router (SIH 2026).
Exposes REST endpoints to verify out-of-band MFA codes and manually trigger challenges.
"""

from typing import Optional

from fastapi import APIRouter, Query

from app.core.mfa_service import MFAService
from app.schemas.telemetry import (
    MfaChallengeResponse,
    MfaVerifyRequest,
    MfaVerifyResponse,
)

router = APIRouter(prefix="/mfa", tags=["Multi-Factor Authentication"])
mfa_service = MFAService.get_instance()


@router.post("/verify-code", response_model=MfaVerifyResponse)
async def verify_mfa_code(payload: MfaVerifyRequest) -> MfaVerifyResponse:
    """
    Validates an out-of-band OTP code submitted by the caller or fraud operations agent.
    If valid, transitions the session state to AUTHENTICATED_OVERRIDE.
    """
    res = await mfa_service.verify_mfa_code(phone_number=payload.phone_number, code=payload.code)

    return MfaVerifyResponse(success=res["success"], message=res["message"], status=res["status"])


@router.post("/dispatch", response_model=MfaChallengeResponse)
async def dispatch_mfa_challenge(
    target_id: str = Query(..., description="Target session ID or speaker ID"),
    phone_number: Optional[str] = Query(None, description="Optional target phone number (E.164)"),
) -> MfaChallengeResponse:
    """
    Triggers an out-of-band MFA challenge subject to the sliding cooldown window.
    """
    res = await mfa_service.dispatch_mfa_challenge(target_id=target_id, phone_number=phone_number)

    return MfaChallengeResponse(
        status=res.get("status", "failed"),
        message=res.get("message", "MFA dispatch processed."),
        remaining_seconds=res.get("remaining_seconds"),
        phone_number=res.get("phone_number"),
    )


@router.get("/cooldown", response_model=dict)
async def get_mfa_cooldown(
    phone_number: str = Query(..., description="Target E.164 phone number to query"),
) -> dict:
    """
    Checks the remaining cooldown seconds for a given target phone number.
    """
    remaining = mfa_service.get_remaining_cooldown(phone_number)
    return {
        "phone_number": phone_number,
        "cooldown_active": remaining > 0.0,
        "remaining_seconds": round(remaining, 1),
    }
