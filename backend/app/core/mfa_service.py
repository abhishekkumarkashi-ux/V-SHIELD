"""
V-SHIELD Automated Multi-Factor Authentication (MFA) & Cooldown Trigger Service (SIH 2026).
Manages out-of-band challenge dispatching via Twilio Verify API with sliding-window cooldown
and zero-credential simulation mode.
"""

import asyncio
import random
import time
from typing import Any, Dict, Optional

import httpx

from app.config import settings


class MFAService:
    """
    Singleton service managing out-of-band MFA verification challenges,
    intelligent sliding-window cooldowns, and Twilio Verify API integration.
    """

    _instance: Optional["MFAService"] = None

    def __init__(self) -> None:
        self.cooldown_seconds: int = settings.MFA_COOLDOWN_SECONDS
        self.is_enabled: bool = settings.MFA_ENABLED
        self._lock = asyncio.Lock()

        # Maps target_id or phone_number -> last_dispatch_timestamp
        self._session_challenges: Dict[str, float] = {}

        # In-memory storage for simulated OTPs: phone_number -> {"code": str, "timestamp": float}
        self._simulated_otps: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> "MFAService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def has_twilio_credentials(self) -> bool:
        """Returns True if full Twilio Verify credentials are configured."""
        return bool(
            settings.TWILIO_ACCOUNT_SID
            and settings.TWILIO_AUTH_TOKEN
            and settings.TWILIO_VERIFY_SERVICE_SID
        )

    @staticmethod
    def normalize_phone(phone: Optional[str]) -> str:
        """
        Normalizes phone numbers by stripping whitespace, handling URL-decoded '+' signs,
        and ensuring consistent E.164 representation.
        """
        if not phone:
            return settings.DEFAULT_MFA_TARGET_PHONE
        p = phone.strip().replace(" ", "")
        if not p.startswith("+") and not p.startswith("0") and len(p) >= 10:
            p = "+" + p
        return p

    def get_remaining_cooldown(self, key: str) -> float:
        """Calculates remaining seconds in the sliding cooldown window."""
        norm_key = self.normalize_phone(key) if any(c.isdigit() for c in key) else key
        last_time = max(
            self._session_challenges.get(key, 0.0), self._session_challenges.get(norm_key, 0.0)
        )
        elapsed = time.time() - last_time
        remaining = self.cooldown_seconds - elapsed
        return max(0.0, remaining)

    def reset_cooldown(self, key: Optional[str] = None) -> None:
        """Resets the cooldown for a given key, or clears all cooldowns if key is None."""
        if key:
            norm_key = self.normalize_phone(key) if any(c.isdigit() for c in key) else key
            self._session_challenges.pop(key, None)
            self._session_challenges.pop(norm_key, None)
            self._simulated_otps.pop(key, None)
            self._simulated_otps.pop(norm_key, None)
        else:
            self._session_challenges.clear()
            self._simulated_otps.clear()

    async def dispatch_mfa_challenge(
        self, target_id: str, phone_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dispatches an out-of-band challenge (SMS/Voice OTP) if not in cooldown.
        Args:
            target_id: Session ID or registered speaker_id.
            phone_number: Target E.164 phone number. Defaults to DEFAULT_MFA_TARGET_PHONE.
        Returns:
            Dict containing status ("dispatched" | "cooldown_active" | "failed" | "disabled").
        """
        if not self.is_enabled:
            return {"status": "disabled", "message": "MFA trigger system is disabled."}

        target_phone = self.normalize_phone(phone_number or settings.DEFAULT_MFA_TARGET_PHONE)
        lookup_key = target_phone

        async with self._lock:
            remaining = self.get_remaining_cooldown(lookup_key)
            if remaining > 0.0:
                print(f"[MFAService] Cooldown active for {lookup_key}: {remaining:.1f}s remaining.")
                return {
                    "status": "cooldown_active",
                    "remaining_seconds": round(remaining, 1),
                    "phone_number": target_phone,
                    "message": f"MFA challenge cooldown active ({round(remaining, 1)}s remaining).",
                }

            # Mark dispatch timestamp immediately to enforce cooldown
            now = time.time()
            self._session_challenges[lookup_key] = now
            self._session_challenges[target_id] = now

        # 1. Live Twilio Verify Dispatch
        if self.has_twilio_credentials:
            try:
                url = f"https://verify.twilio.com/v2/Services/{settings.TWILIO_VERIFY_SERVICE_SID}/Verifications"
                auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                payload = {"To": target_phone, "Channel": "sms"}

                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, auth=auth, data=payload)
                    if resp.status_code in (200, 201):
                        data = resp.json()
                        sid = data.get("sid", "N/A")
                        print(
                            f"[MFAService] Successfully dispatched Twilio Verify challenge (SID: {sid}) to {target_phone}"
                        )
                        return {
                            "status": "dispatched",
                            "phone_number": target_phone,
                            "sid": sid,
                            "message": f"Twilio Verify MFA challenge sent to {target_phone} via SMS.",
                        }
                    else:
                        print(
                            f"[MFAService] Twilio Verify dispatch error {resp.status_code}: {resp.text}"
                        )
                        return {
                            "status": "failed",
                            "error": resp.text,
                            "message": f"Twilio Verify failed with HTTP {resp.status_code}.",
                        }
            except Exception as exc:
                print(f"[MFAService] Twilio request exception ({exc}).")
                return {
                    "status": "failed",
                    "error": str(exc),
                    "message": f"Twilio connection error: {exc}",
                }

        # 2. Simulated Out-of-Band Dispatch (Zero Credentials Fallback)
        sim_code = f"{random.randint(100000, 999999)}"
        self._simulated_otps[target_phone] = {"code": sim_code, "timestamp": time.time()}
        print(
            f"[SIMULATED_MFA] Dispatched 6-digit challenge to {target_phone} (Simulated OTP: {sim_code} or '000000')"
        )
        return {
            "status": "dispatched",
            "phone_number": target_phone,
            "simulated": True,
            "message": f"[SIMULATED] Out-of-band MFA challenge dispatched to {target_phone}.",
        }

    async def verify_mfa_code(self, phone_number: str, code: str) -> Dict[str, Any]:
        """
        Validates an OTP code submitted by the user/caller.
        Args:
            phone_number: Target phone number.
            code: 6-digit verification code.
        Returns:
            Dict containing success (bool), message (str), and status.
        """
        code = str(code).strip()
        target_phone = self.normalize_phone(phone_number or settings.DEFAULT_MFA_TARGET_PHONE)

        # 1. Live Twilio Verify Check
        if self.has_twilio_credentials:
            try:
                url = f"https://verify.twilio.com/v2/Services/{settings.TWILIO_VERIFY_SERVICE_SID}/VerificationCheck"
                auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                payload = {"To": target_phone, "Code": code}

                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, auth=auth, data=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("status") == "approved":
                            # Reset cooldown on successful verification
                            self.reset_cooldown(target_phone)
                            return {
                                "success": True,
                                "status": "AUTHENTICATED_OVERRIDE",
                                "message": "Twilio Verify MFA approved. Authorized caller verified.",
                            }
                    return {
                        "success": False,
                        "status": "FAILED",
                        "message": "Invalid or expired Twilio Verify code.",
                    }
            except Exception as err:
                print(f"[MFAService] Twilio verification check error: {err}")
                return {
                    "success": False,
                    "status": "FAILED",
                    "message": f"Twilio verification error: {err}",
                }

        # 2. Simulated Verification
        # Accepts '000000' as universal master bypass, or the active generated OTP
        active_sim = self._simulated_otps.get(target_phone)
        is_match = (code == "000000") or (active_sim and active_sim.get("code") == code)

        if is_match:
            self.reset_cooldown(target_phone)
            return {
                "success": True,
                "status": "AUTHENTICATED_OVERRIDE",
                "message": "MFA code verified successfully. Session identity authenticated.",
            }

        return {
            "success": False,
            "status": "FAILED",
            "message": "Invalid verification code provided. Please check the code and try again.",
        }
