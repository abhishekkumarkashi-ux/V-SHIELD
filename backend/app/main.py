"""
V-SHIELD Backend Application (SIH 2026 - Problem Statement ID: 26104).
FastAPI Real-Time Voice Integrity & Fraud Prevention Gateway.
WebSocket Ingestion (/ws/live-call) & Biometric Speaker Verification.
"""

import time
from typing import Optional

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.buffer import AudioCircularBuffer
from app.core.risk_engine import RiskEngine
from app.core.vad import MarginPreservingVAD
from app.models.aasist_service import AASISTService
from app.models.ecapa_service import ECAPAService
from app.schemas.telemetry import (
    SpeakerEnrollResponse,
    SpeakerProfile,
    SystemHealthResponse,
    TelemetryMetrics,
    TelemetryPacket,
)

app = FastAPI(
    title="V-SHIELD Voice Security Platform",
    version=settings.VERSION,
    description="Real-Time AI Voice Impersonation Detection & Fraud Prevention Platform",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Eagerly initialize core AI services
aasist_service = AASISTService.get_instance()
ecapa_service = ECAPAService.get_instance()
from app.core.mfa_service import MFAService

mfa_service = MFAService.get_instance()

# Mount API Routers
from app.routers.analyze import router as analyze_router
from app.routers.mfa import router as mfa_router

app.include_router(analyze_router, prefix="/api/v1")
app.include_router(mfa_router, prefix="/api/v1")


@app.get("/api/health", response_model=SystemHealthResponse)
async def get_health() -> SystemHealthResponse:
    """Returns platform operational readiness, device, and model statuses."""
    speakers = ecapa_service.get_enrolled_speakers()
    return SystemHealthResponse(
        status="ONLINE",
        version=settings.VERSION,
        device=aasist_service.device,
        aasist_loaded=aasist_service.is_loaded or aasist_service.is_onnx_loaded,
        ecapa_loaded=ecapa_service.is_loaded or ecapa_service.is_onnx_loaded,
        enrolled_speakers_count=len(speakers),
        aasist_onnx_loaded=aasist_service.is_onnx_loaded,
        ecapa_onnx_loaded=ecapa_service.is_onnx_loaded,
    )


@app.get("/api/speakers", response_model=list[SpeakerProfile])
async def list_speakers() -> list[SpeakerProfile]:
    """Retrieves all registered speaker profiles."""
    speakers = ecapa_service.get_enrolled_speakers()
    return [
        SpeakerProfile(
            speaker_id=s["speaker_id"],
            name=s.get("name"),
            enrolled_at=s.get("enrolled_at", time.time()),
        )
        for s in speakers
    ]


@app.post("/api/speakers/enroll", response_model=SpeakerEnrollResponse)
async def enroll_speaker(
    speaker_id: str = Form(...),
    name: Optional[str] = Form(None),
    audio_file: UploadFile = File(...),
) -> SpeakerEnrollResponse:
    """Enrolls an authorized caller voiceprint using 16kHz WAV or PCM audio."""
    audio_bytes = await audio_file.read()
    if len(audio_bytes) < 16000:
        raise HTTPException(
            status_code=400,
            detail="Audio sample too short. Please provide at least 1-2 seconds of clear voice audio.",
        )

    # If it is a WAV file, strip headers if present
    if audio_bytes[:4] == b"RIFF":
        raw_pcm = audio_bytes[44:]
    else:
        raw_pcm = audio_bytes

    embedding = ecapa_service.enroll_speaker(
        speaker_id=speaker_id, audio=raw_pcm, name=name or speaker_id
    )

    return SpeakerEnrollResponse(
        success=True,
        speaker_id=speaker_id,
        message=f"Voiceprint for '{name or speaker_id}' registered successfully.",
        embedding_dim=len(embedding),
    )


@app.websocket("/ws/live-call")
async def websocket_live_call(
    websocket: WebSocket,
    speaker_id: Optional[str] = Query(None, description="Enrolled speaker ID to verify against"),
    sample_rate: int = Query(16000, description="Input sample rate (e.g. 16000 or 8000)"),
    target_phone: Optional[str] = Query(
        None, description="Target phone number for MFA challenge dispatch"
    ),
):
    """
    Real-Time Audio Ingestion & Telemetry Streaming Gateway.
    Receives: Binary PCM16 mono audio chunks.
    Sends: Structured JSON TelemetryPacket every 8,000 samples (~0.5s).
    """
    await websocket.accept()

    # Create dedicated per-session audio buffer, VAD, and risk state
    buffer = AudioCircularBuffer(
        capacity=settings.WINDOW_SIZE,
        hop_size=settings.HOP_SIZE,
        target_sample_rate=settings.SAMPLE_RATE,
    )
    vad = MarginPreservingVAD(
        sample_rate=settings.SAMPLE_RATE, min_silence_padding_sec=settings.VAD_MARGIN_SEC
    )
    risk_engine = RiskEngine(alpha=settings.RISK_ALPHA)

    active_speaker_id = speaker_id
    active_target_phone = target_phone or settings.DEFAULT_MFA_TARGET_PHONE

    try:
        while True:
            # Client can stream binary audio or JSON configuration packets
            message = await websocket.receive()

            if "bytes" in message and message["bytes"]:
                raw_chunk = message["bytes"]
                buffer.append_pcm16_bytes(raw_chunk, input_sample_rate=sample_rate)

                # Process all complete hop windows ready in the ring buffer
                for window_tensor in buffer.extract_all_ready_windows():
                    t_start = time.perf_counter()

                    # 1. Voice Activity Detection Guard (Preserves 300ms silence margins)
                    is_speech_active, speech_ratio, safe_audio = vad.process_window(window_tensor)

                    # 2. AASIST Anti-Spoofing Inference (RawLogits & Softmax Spoof Prob)
                    _, spoof_prob = aasist_service.predict(safe_audio)

                    # 3. ECAPA-TDNN Speaker Biometric Verification
                    speaker_similarity = None
                    if active_speaker_id:
                        speaker_similarity = ecapa_service.verify_speaker(
                            safe_audio, active_speaker_id
                        )

                    # 4. Multi-Signal Fusion & Dynamic Risk Aggregation
                    risk_score, classification, recommended_action = risk_engine.evaluate(
                        spoof_prob=spoof_prob,
                        speaker_similarity=speaker_similarity,
                        is_speech_active=is_speech_active,
                    )

                    # 4b. Layer 5 Automated Out-of-Band MFA Dispatch with Sliding Cooldown
                    mfa_status = "NONE"
                    if RiskEngine.should_trigger_mfa(risk_score, recommended_action):
                        mfa_res = await mfa_service.dispatch_mfa_challenge(
                            target_id=active_speaker_id or "session",
                            phone_number=active_target_phone,
                        )
                        status_val = mfa_res.get("status")
                        if status_val == "dispatched":
                            mfa_status = "DISPATCHED"
                        elif status_val == "cooldown_active":
                            mfa_status = "COOLDOWN"

                    rms_energy = buffer.get_current_rms()
                    latency_ms = round((time.perf_counter() - t_start) * 1000.0, 2)

                    # 5. Broadcast Telemetry Packet to Client
                    packet = TelemetryPacket(
                        timestamp=time.time(),
                        risk_score=risk_score,
                        classification=classification,
                        metrics=TelemetryMetrics(
                            spoof_probability=round(spoof_prob, 4),
                            speaker_similarity=(
                                round(speaker_similarity, 4)
                                if speaker_similarity is not None
                                else 0.0
                            ),
                            buffer_energy_rms=round(rms_energy, 4),
                            vad_speech_ratio=round(speech_ratio, 4),
                            latency_ms=latency_ms,
                        ),
                        recommended_action=recommended_action,
                        mfa_status=mfa_status,
                    )

                    await websocket.send_text(packet.model_dump_json())

            elif "text" in message and message["text"]:
                # Text payload for on-the-fly caller switching or reset
                import json

                try:
                    payload = json.loads(message["text"])
                    if "speaker_id" in payload:
                        active_speaker_id = payload["speaker_id"]
                    if "target_phone" in payload:
                        active_target_phone = payload["target_phone"]
                    if payload.get("action") == "reset":
                        buffer.reset()
                        risk_engine.reset()
                except Exception:
                    pass

    except WebSocketDisconnect:
        pass
    except Exception as err:
        print(f"[WebSocket Error] Exception in /ws/live-call: {err}")
    finally:
        buffer.reset()
        risk_engine.reset()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
