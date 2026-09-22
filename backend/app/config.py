import logging
import os
from pathlib import Path
from typing import List, Optional, Union

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("vshield.config")

# Project root resolution for robust local development environment loading
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
ROOT_ENV_PATH: Path = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    PROJECT_NAME: str = "V-SHIELD"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # "development", "staging", "production", "test"

    # Audio Ingestion & Buffer Constraints
    SAMPLE_RATE: int = 16000  # 16 kHz Mono
    NARROWBAND_SAMPLE_RATE: int = 8000  # 8 kHz PSTN / Asterisk telephony
    WINDOW_SIZE: int = 64600  # nb_samp = 64600 samples (~4.0375s) for AASIST
    HOP_SIZE: int = 8000  # 8,000 samples (~0.5s sliding window)

    # VAD Margin Preservation (Silence Shortcut Mitigation - ASVspoof 2021)
    VAD_MARGIN_SEC: float = 0.30  # 300 ms ambient margin preservation
    VAD_ENERGY_THRESHOLD: float = 0.005  # RMS energy threshold for speech trigger

    # Risk Engine Hyperparameters
    RISK_ALPHA: float = 0.70  # EMA smoothing factor
    SPOOF_DECISION_THRESHOLD: float = 0.50  # Hard decision boundary between bona fide and spoof
    SPOOF_HIGH_THRESH: float = 0.65  # P(spoof) threshold for clone/synthetic attack
    SPOOF_LOW_THRESH: float = 0.30  # P(spoof) threshold for genuine caller
    SIMILARITY_HIGH_THRESH: float = 0.70  # ECAPA cosine sim threshold for match
    SIMILARITY_LOW_THRESH: float = 0.40  # ECAPA cosine sim threshold for mismatch

    # Model Weights & Storage Paths
    BASE_DIR: Path = Path(__file__).resolve().parent
    WEIGHTS_DIR: Path = BASE_DIR / "weights"
    VSHIELD_ANTISPOOF_MODEL_PATH: Optional[Path] = None
    AASIST_WEIGHTS_PATH: Path = WEIGHTS_DIR / "AASIST.pth"
    AASIST_ONNX_PATH: Path = WEIGHTS_DIR / "aasist_fp16.onnx"
    ECAPA_ONNX_PATH: Path = WEIGHTS_DIR / "ecapa_fp16.onnx"
    SPEAKERS_DB_PATH: Path = BASE_DIR / "vshield.db"

    # MFA & Twilio Inbound Telephony Configuration (SIH 2026)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_VERIFY_SERVICE_SID: Optional[str] = None
    TWILIO_PUBLIC_BASE_URL: Optional[str] = None  # e.g. https://example.ngrok-free.app
    MFA_COOLDOWN_SECONDS: int = 120  # 2 minutes sliding cooldown
    MFA_ENABLED: bool = True
    DEFAULT_MFA_TARGET_PHONE: Optional[str] = None

    # CORS Allowed Origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Authentication & Session Security (SIH 2026)
    JWT_SECRET_KEY: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    SESSION_IDLE_TIMEOUT_SECONDS: int = 300  # 5 minutes idle timeout
    SESSION_MAX_DURATION_SECONDS: int = 3600  # 1 hour max session lifetime
    DEMO_OPERATOR_USERNAME: str = "analyst@vshield.internal"
    DEMO_OPERATOR_PASSWORD: Optional[str] = None

    # Network & Deployment Topology
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    BACKEND_URL: str = "http://localhost:8000"
    DATABASE_URL: Optional[str] = None

    # Google OAuth 2.0 / OpenID Connect (Configurable)
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    FRONTEND_URL: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=(str(ROOT_ENV_PATH), ".env"),
        env_file_encoding="utf-8",
        extra="allow",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            if value.strip().startswith("[") and value.strip().endswith("]"):
                import json

                try:
                    return json.loads(value)
                except Exception:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        # Handle JWT_SECRET_KEY
        if not self.JWT_SECRET_KEY:
            if self.ENVIRONMENT.lower() in ("production", "prod"):
                raise ValueError(
                    "CRITICAL SECURITY ERROR: JWT_SECRET_KEY must be set in production!"
                )
            self.JWT_SECRET_KEY = "vshield-dev-insecure-secret-key-change-in-production"
            logger.warning(
                "[SECURITY WARNING] Using development-only JWT_SECRET_KEY. "
                "Set the JWT_SECRET_KEY environment variable in production."
            )

        # Handle DEMO_OPERATOR_PASSWORD
        if not self.DEMO_OPERATOR_PASSWORD:
            if self.ENVIRONMENT.lower() in ("production", "prod"):
                raise ValueError(
                    "CRITICAL SECURITY ERROR: DEMO_OPERATOR_PASSWORD must be set in production!"
                )
            self.DEMO_OPERATOR_PASSWORD = "VShieldDev2026!"

        # Handle DEFAULT_MFA_TARGET_PHONE fallback
        if not self.DEFAULT_MFA_TARGET_PHONE:
            self.DEFAULT_MFA_TARGET_PHONE = os.getenv("DEFAULT_MFA_TARGET_PHONE", "+919876543210")

        # Validate CORS: Disallow wildcard with credentials
        if "*" in self.CORS_ORIGINS:
            if self.ENVIRONMENT.lower() in ("production", "prod"):
                raise ValueError(
                    "CRITICAL SECURITY ERROR: Wildcard CORS origin ('*') is disallowed in production with credentials."
                )
            logger.warning(
                "[SECURITY WARNING] Wildcard '*' found in CORS_ORIGINS. "
                "Restricting to explicit local development origins."
            )
            self.CORS_ORIGINS = [origin for origin in self.CORS_ORIGINS if origin != "*"]
            if not self.CORS_ORIGINS:
                self.CORS_ORIGINS = [
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                    "http://localhost:3000",
                ]

        # Ensure FRONTEND_URL is included in authorized CORS origins
        if self.FRONTEND_URL and self.FRONTEND_URL.startswith("http"):
            clean_origin = self.FRONTEND_URL.strip().rstrip("/")
            if clean_origin and clean_origin not in self.CORS_ORIGINS:
                self.CORS_ORIGINS.append(clean_origin)

        return self


settings = Settings()
