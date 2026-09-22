"""
Telemetry & API schemas for V-SHIELD.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TelemetryMetrics(BaseModel):
    spoof_probability: float = Field(
        ..., ge=0.0, le=1.0, description="AASIST probability of audio being synthetic/spoofed"
    )
    speaker_similarity: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="ECAPA-TDNN cosine similarity against enrolled speaker, or None if unenrolled",
    )
    speaker_status: Optional[str] = Field(
        default="NO_VOICEPRINT",
        description="ECAPA speaker verification state (VERIFIED, MISMATCH, EVALUATING, NO_VOICEPRINT)",
    )
    buffer_energy_rms: float = Field(
        ..., ge=0.0, description="Root-mean-square energy of the active sliding window"
    )
    vad_speech_ratio: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Proportion of frames identified as active speech (with margins)",
    )
    latency_ms: Optional[float] = Field(
        None, description="End-to-end window inference latency in milliseconds"
    )


class PerformanceTelemetry(BaseModel):
    preprocess_ms: float = Field(default=0.0, description="Audio preprocessing and VAD time in ms")
    aasist_ms: float = Field(default=0.0, description="AASIST inference latency in ms")
    ecapa_ms: float = Field(default=0.0, description="ECAPA speaker verification latency in ms")
    risk_engine_ms: float = Field(default=0.0, description="Risk engine fusion latency in ms")
    total_ms: float = Field(default=0.0, description="Total window processing latency in ms")
    provider: str = Field(
        default="CPUExecutionProvider", description="Active ONNX execution provider"
    )
    device: str = Field(default="cpu", description="Active compute device (cuda/cpu)")
    performance_status: Literal["OPTIMAL", "DEGRADED"] = Field(
        default="OPTIMAL", description="Performance health against hop budget"
    )
    hop_budget_ms: float = Field(default=500.0, description="Target audio hop budget in ms")
    actual_p50_ms: Optional[float] = Field(
        default=None, description="Rolling actual p50 latency in ms"
    )


class TelemetryPacket(BaseModel):
    timestamp: float = Field(..., description="Unix epoch timestamp in seconds")
    risk_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Multi-signal fused risk score (0-100), or None during insufficient data or warmup",
    )
    classification: Literal["LOW_RISK", "MEDIUM_RISK", "HIGH_RISK", "INSUFFICIENT_DATA"] = Field(
        ..., description="Tri-tier threat level or insufficient data state"
    )
    decision: Optional[str] = Field(
        default=None,
        description="Explainable decision status (e.g. LOW_RISK, ELEVATED_RISK, HIGH_RISK, INSUFFICIENT_DATA)",
    )
    factors: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Explainable multi-signal risk breakdown factors"
    )
    metrics: TelemetryMetrics
    recommended_action: Literal[
        "ALLOW_CALL",
        "MONITOR",
        "FLAG_OPERATOR_VERIFICATION",
        "STEP_UP_AUTH",
        "TRIGGER_MFA_CALLBACK",
        "QUARANTINE_TRANSACTION",
        "TERMINATE_AND_ALERT",
    ] = Field(..., description="Automated mitigation decision triggered by the Risk Engine")
    mfa_status: Literal["NONE", "DISPATCHED", "COOLDOWN"] = Field(
        default="NONE", description="Out-of-band MFA automated trigger status"
    )
    status: Literal["success", "error"] = Field(
        default="success", description="Inference execution status"
    )
    pipeline_status: Optional[str] = Field(
        default="ANALYZING", description="Pipeline execution state"
    )
    speaker_status: Optional[str] = Field(
        default="NO_VOICEPRINT", description="Speaker verification state"
    )
    latency: Optional[Dict[str, float]] = Field(
        default=None, description="Detailed stage latency breakdown in milliseconds"
    )
    performance: Optional[PerformanceTelemetry] = Field(
        default=None, description="Detailed runtime inference performance telemetry"
    )
    performance_status: Optional[str] = Field(
        default="OPTIMAL", description="Hop budget compliance: OPTIMAL or DEGRADED"
    )


class SpeakerEnrollRequest(BaseModel):
    speaker_id: str = Field(
        ..., min_length=1, max_length=64, description="Unique identifier for the registered speaker"
    )
    name: Optional[str] = Field(
        None, max_length=128, description="Full name or role of the speaker"
    )


class SpeakerEnrollResponse(BaseModel):
    success: bool
    speaker_id: str
    message: str
    embedding_dim: int = 192


class SpeakerProfile(BaseModel):
    speaker_id: str
    name: Optional[str] = None
    enrolled_at: float
    sample_count: int = 1


class SystemHealthResponse(BaseModel):
    status: str = Field(..., description="Overall health status ('ok', 'degraded', or 'error')")
    model_loaded: bool = Field(
        ..., description="True if core AI inference models are loaded and ready"
    )
    device: str = Field(..., description="Active execution device ('cuda' or 'cpu')")
    anti_spoof_model: str = Field(
        ..., description="Name and runtime of the active anti-spoof model"
    )
    speaker_verification_loaded: bool = Field(
        ..., description="True if speaker verification model is loaded and ready"
    )
    version: str = Field(default="1.0.0", description="V-SHIELD platform version")
    aasist_loaded: bool = Field(default=False, description="AASIST model availability")
    ecapa_loaded: bool = Field(default=False, description="ECAPA-TDNN model availability")
    enrolled_speakers_count: int = Field(
        default=0, description="Number of enrolled biometric profiles"
    )
    aasist_onnx_loaded: bool = Field(default=False, description="AASIST ONNX session status")
    ecapa_onnx_loaded: bool = Field(default=False, description="ECAPA ONNX session status")
    cuda_available: bool = Field(
        default=False, description="Whether CUDA acceleration is available"
    )
    details: Optional[dict] = Field(
        default=None, description="Detailed diagnostics or load error info"
    )


class AnalyzeTelemetry(BaseModel):
    spoof_probability: float = Field(
        ..., ge=0.0, le=1.0, description="AASIST probability of audio being synthetic/spoofed"
    )
    speaker_similarity: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="ECAPA-TDNN cosine similarity between reference and test audio",
    )


class AnalyzeFileResponse(BaseModel):
    status: str = Field(default="success", description="Status code or indicator")
    risk_score: float = Field(
        ..., ge=0.0, le=100.0, description="Calculated 0-100 Impersonation Risk Score"
    )
    classification: str = Field(..., description="High-level threat classification")
    telemetry: AnalyzeTelemetry = Field(..., description="Acoustic & biometric model telemetry")
    message: str = Field(..., description="Descriptive fraud decision and action guidance")


class MfaVerifyRequest(BaseModel):
    phone_number: str = Field(..., description="E.164 phone number of the target caller")
    code: str = Field(
        ..., min_length=4, max_length=10, description="Verification code received by caller"
    )


class MfaVerifyResponse(BaseModel):
    success: bool
    message: str
    status: Literal["AUTHENTICATED_OVERRIDE", "FAILED", "COOLDOWN_ACTIVE"]


class MfaChallengeResponse(BaseModel):
    status: Literal["dispatched", "cooldown_active", "failed", "disabled"]
    message: str
    remaining_seconds: Optional[float] = None
    phone_number: Optional[str] = None


class AudioMetricsPacket(BaseModel):
    type: Literal["audio_metrics"] = "audio_metrics"
    sample_rate: int = Field(default=16000, description="Sampling rate in Hz")
    samples: int = Field(..., description="Sample count in chunk")
    duration_ms: float = Field(..., description="Duration of chunk in milliseconds")
    rms: float = Field(..., description="RMS volume level")
    peak: float = Field(..., description="Peak amplitude")
    pipeline_status: Optional[str] = Field(
        default=None,
        description="Current audio pipeline state ('LISTENING', 'WAITING_FOR_AUDIO', 'WARMING_UP', etc.)",
    )
    speech_state: Optional[str] = Field(
        default=None, description="Acoustic VAD state on chunk ('SPEECH' or 'SILENCE')"
    )
    status: Optional[str] = Field(
        default=None, description="Pipeline status indicator (e.g. 'warming_up', 'listening')"
    )
    buffered_seconds: Optional[float] = Field(
        default=None, description="Buffered audio accumulation in seconds"
    )
    required_seconds: Optional[float] = Field(
        default=None, description="Required seconds for full inference window"
    )
