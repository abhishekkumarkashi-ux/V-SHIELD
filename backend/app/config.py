"""
V-SHIELD Configuration & Hyperparameters (SIH 2026).
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "V-SHIELD"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    DEBUG: bool = False

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
    SPOOF_HIGH_THRESH: float = 0.65  # P(spoof) threshold for clone/synthetic attack
    SPOOF_LOW_THRESH: float = 0.30  # P(spoof) threshold for genuine caller
    SIMILARITY_HIGH_THRESH: float = 0.70  # ECAPA cosine sim threshold for match
    SIMILARITY_LOW_THRESH: float = 0.40  # ECAPA cosine sim threshold for mismatch

    # Model Weights & Storage Paths
    BASE_DIR: Path = Path(__file__).resolve().parent
    WEIGHTS_DIR: Path = BASE_DIR / "weights"
    AASIST_WEIGHTS_PATH: Path = WEIGHTS_DIR / "AASIST.pth"
    AASIST_ONNX_PATH: Path = WEIGHTS_DIR / "aasist_fp16.onnx"
    ECAPA_ONNX_PATH: Path = WEIGHTS_DIR / "ecapa_fp16.onnx"
    SPEAKERS_DB_PATH: Path = BASE_DIR / "vshield.db"

    # MFA & Twilio Verify Configuration (SIH 2026)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_VERIFY_SERVICE_SID: Optional[str] = None
    MFA_COOLDOWN_SECONDS: int = 120  # 2 minutes sliding cooldown
    MFA_ENABLED: bool = True
    DEFAULT_MFA_TARGET_PHONE: str = "+919876543210"

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


settings = Settings()
