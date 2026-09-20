"""
V-SHIELD Backend Application (SIH 2026 - Problem Statement ID: 26104).
FastAPI Real-Time Voice Integrity & Fraud Prevention Gateway.
WebSocket Ingestion (/ws/live-call) & Biometric Speaker Verification.
"""

import json
import sys
import time
from typing import Optional

import numpy as np
import torch
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
    AudioMetricsPacket,
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


def print_startup_banner() -> None:
    """Logs structured system capability and model readiness banner."""
    cuda_avail = torch.cuda.is_available()
    cuda_device = torch.cuda.get_device_name(0) if cuda_avail else "N/A"

    aasist_loaded = bool(aasist_service.is_onnx_loaded or aasist_service.is_loaded)
    if aasist_service.is_onnx_loaded:
        anti_spoof_desc = f"AASIST Graph Attention (ONNX Runtime FP16 - {settings.AASIST_ONNX_PATH.name})"
    elif aasist_service.is_loaded:
        anti_spoof_desc = f"AASIST Graph Attention (PyTorch - {settings.AASIST_WEIGHTS_PATH.name})"
    else:
        anti_spoof_desc = f"AASIST Not Loaded ({getattr(aasist_service, 'load_error', 'Missing weights')})"

    ecapa_loaded = bool(ecapa_service.is_onnx_loaded or ecapa_service.is_loaded)
    if ecapa_service.is_onnx_loaded:
        ecapa_desc = f"ECAPA-TDNN 192-dim (ONNX Runtime FP16 - {settings.ECAPA_ONNX_PATH.name})"
    elif ecapa_service.is_loaded:
        ecapa_desc = "ECAPA-TDNN (SpeechBrain PyTorch)"
    else:
        ecapa_desc = "ECAPA-TDNN (Offline acoustic signature)"

    banner = f"""
==================================================
V-SHIELD BACKEND STARTUP
==================================================
Python:                     {sys.version.split()[0]}
PyTorch:                    {torch.__version__}
CUDA available:             {cuda_avail}
CUDA device:                {cuda_device}
Active Execution Device:    {aasist_service.device}
Anti-spoof model:           {anti_spoof_desc}
Anti-spoof model loaded:    {aasist_loaded}
Speaker verification:       {ecapa_desc}
Speaker verification loaded:{ecapa_loaded}
Risk engine:                Multi-Signal EMA Fusion (alpha={settings.RISK_ALPHA})
Risk engine loaded:         True
Enrolled speakers:          {len(ecapa_service.get_enrolled_speakers())} profiles
==================================================
"""
    print(banner.strip(), flush=True)


@app.on_event("startup")
async def startup_event() -> None:
    print_startup_banner()


@app.get("/health", response_model=SystemHealthResponse)
@app.get("/api/health", response_model=SystemHealthResponse)
async def get_health() -> SystemHealthResponse:
    """Returns platform operational readiness, device, and truthful model statuses."""
    aasist_ready = bool(aasist_service.is_onnx_loaded or aasist_service.is_loaded)
    ecapa_ready = bool(ecapa_service.is_onnx_loaded or ecapa_service.is_loaded)
    models_ready = bool(aasist_ready and ecapa_ready)

    if aasist_service.is_onnx_loaded:
        anti_spoof_name = "AASIST (ONNX FP16)"
    elif aasist_service.is_loaded:
        anti_spoof_name = "AASIST (PyTorch)"
    else:
        anti_spoof_name = "None (AASIST Not Loaded)"

    status_str = "ok" if models_ready else ("degraded" if (aasist_ready or ecapa_ready) else "error")
    speakers = ecapa_service.get_enrolled_speakers()

    details = {}
    if getattr(aasist_service, "load_error", None) and not aasist_ready:
        details["aasist_error"] = str(aasist_service.load_error)
    if getattr(ecapa_service, "load_error", None) and not ecapa_ready:
        details["ecapa_error"] = str(ecapa_service.load_error)

    return SystemHealthResponse(
        status=status_str,
        model_loaded=models_ready,
        device=aasist_service.device,
        anti_spoof_model=anti_spoof_name,
        speaker_verification_loaded=ecapa_ready,
        version=settings.VERSION,
        aasist_loaded=aasist_ready,
        ecapa_loaded=ecapa_ready,
        enrolled_speakers_count=len(speakers),
        aasist_onnx_loaded=aasist_service.is_onnx_loaded,
        ecapa_onnx_loaded=ecapa_service.is_onnx_loaded,
        cuda_available=torch.cuda.is_available(),
        details=details if details else None,
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
@app.websocket("/ws/analyze")
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
    Mounted at both /ws/live-call and /ws/analyze.
    Receives: Binary PCM audio chunks or structured JSON control packets.
    Sends: Structured JSON TelemetryPacket / Session status events.
    """
    await websocket.accept()
    session_id = f"sess_{int(time.time() * 1000)}"
    endpoint_path = websocket.url.path
    print(f"[WS] Client connected to {endpoint_path} (session={session_id})")

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
    active_audio_format = None
    session_active = False
    pipeline_state = "READY"
    last_metrics_report_time = 0.0

    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message:
                raw_chunk = message.get("bytes") or b""
                if len(raw_chunk) == 0:
                    await websocket.send_text(
                        json.dumps({"type": "audio_error", "error": "Empty audio packet received"})
                    )
                    continue

                if len(raw_chunk) < 4:
                    await websocket.send_text(
                        json.dumps({
                            "type": "audio_error",
                            "error": f"Audio packet too small: expected >= 4 bytes (got {len(raw_chunk)})",
                        })
                    )
                    continue

                # Check frame alignment
                if active_audio_format == "float32" and len(raw_chunk) % 4 != 0:
                    await websocket.send_text(
                        json.dumps({
                            "type": "audio_error",
                            "error": f"Malformed Float32 audio packet: length {len(raw_chunk)} not divisible by 4",
                        })
                    )
                    continue
                elif active_audio_format == "pcm16" and len(raw_chunk) % 2 != 0:
                    await websocket.send_text(
                        json.dumps({
                            "type": "audio_error",
                            "error": f"Malformed PCM16 audio packet: length {len(raw_chunk)} not divisible by 2",
                        })
                    )
                    continue
                elif active_audio_format is None and (
                    len(raw_chunk) % 4 != 0 and len(raw_chunk) % 2 != 0
                ):
                    await websocket.send_text(
                        json.dumps({
                            "type": "audio_error",
                            "error": f"Malformed audio packet: length {len(raw_chunk)} not aligned to sample frame size",
                        })
                    )
                    continue

                # Convert to Float32 array and validate numerical properties
                is_f32 = active_audio_format == "float32" or (
                    active_audio_format is None and len(raw_chunk) % 4 == 0
                )

                audio_samples = None
                if is_f32:
                    try:
                        candidate = np.frombuffer(raw_chunk, dtype=np.float32)
                        if not np.all(np.isfinite(candidate)):
                            if active_audio_format == "float32":
                                await websocket.send_text(
                                    json.dumps({
                                        "type": "audio_error",
                                        "error": "Non-finite values (NaN / Inf) detected in Float32 audio stream",
                                    })
                                )
                                continue
                            else:
                                is_f32 = False
                        else:
                            max_amp = (
                                float(np.max(np.abs(candidate))) if len(candidate) > 0 else 0.0
                            )
                            if max_amp > 10.0:
                                if active_audio_format == "float32":
                                    await websocket.send_text(
                                        json.dumps({
                                            "type": "audio_error",
                                            "error": f"Float32 audio amplitude out of bounds (peak: {max_amp:.2f} > 10.0)",
                                        })
                                    )
                                    continue
                                else:
                                    is_f32 = False
                            else:
                                audio_samples = candidate.copy()
                    except Exception as parse_err:
                        if active_audio_format == "float32":
                            await websocket.send_text(
                                json.dumps({
                                    "type": "audio_error",
                                    "error": f"Failed to parse Float32 audio chunk: {parse_err}",
                                })
                            )
                            continue
                        is_f32 = False

                if audio_samples is None:
                    # Ingest as PCM16 fallback
                    try:
                        valid_len = (len(raw_chunk) // 2) * 2
                        int16_arr = np.frombuffer(raw_chunk[:valid_len], dtype=np.int16)
                        audio_samples = (int16_arr.astype(np.float32) / 32768.0).copy()
                    except Exception as pcm_err:
                        await websocket.send_text(
                            json.dumps({
                                "type": "audio_error",
                                "error": f"Failed to parse PCM16 audio chunk: {pcm_err}",
                            })
                        )
                        continue

                # Safety clamp to [-1.0, 1.0]
                audio_samples = np.clip(audio_samples, -1.0, 1.0)

                # Compute chunk metrics
                sample_count = len(audio_samples)
                duration_ms = round((sample_count / sample_rate) * 1000.0, 2)
                chunk_rms = float(np.sqrt(np.mean(audio_samples**2))) if sample_count > 0 else 0.0
                chunk_peak = float(np.max(np.abs(audio_samples))) if sample_count > 0 else 0.0

                if not session_active:
                    session_active = True
                if pipeline_state in ("READY", "WAITING_FOR_AUDIO"):
                    pipeline_state = "LISTENING"

                try:
                    buffer.append_samples(audio_samples)
                except Exception as buf_err:
                    await websocket.send_text(
                        json.dumps({
                            "type": "audio_error",
                            "error": f"Audio buffer ingestion failure: {buf_err}",
                        })
                    )
                    continue

                # Process all complete hop windows ready in the ring buffer
                extracted_any = False
                for window_tensor in buffer.extract_all_ready_windows():
                    extracted_any = True
                    pipeline_state = "ANALYZING"
                    t_start = time.perf_counter()

                    try:
                        # 1. Voice Activity Detection Guard (Preserves 300ms silence margins)
                        is_speech_active, speech_ratio, safe_audio = vad.process_window(
                            window_tensor
                        )

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
                                    else None
                                ),
                                buffer_energy_rms=round(rms_energy, 4),
                                vad_speech_ratio=round(speech_ratio, 4),
                                latency_ms=latency_ms,
                            ),
                            recommended_action=recommended_action,
                            mfa_status=mfa_status,
                            status="success",
                            pipeline_status="ANALYZING",
                        )

                        packet_dict = packet.model_dump()
                        packet_dict["type"] = "analysis"
                        packet_dict["session_id"] = session_id
                        packet_dict["anti_spoof"] = {
                            "score": round(spoof_prob, 4),
                        }
                        packet_dict["risk"] = {
                            "score": round(risk_score, 2),
                        }
                        await websocket.send_text(json.dumps(packet_dict))
                    except Exception as model_err:
                        pipeline_state = "ANALYSIS_ERROR"
                        print(f"[WS Error] Inference pipeline failure: {model_err}")
                        await websocket.send_text(
                            json.dumps({
                                "type": "analysis",
                                "status": "error",
                                "pipeline_status": "ANALYSIS_ERROR",
                                "error": f"Inference pipeline failure: {model_err}",
                            })
                        )

                # Instrument and report incoming audio metrics at bounded intervals
                now = time.time()
                should_report_metrics = (
                    not extracted_any
                    and (last_metrics_report_time == 0.0 or now - last_metrics_report_time >= 0.5)
                ) or (now - last_metrics_report_time >= 1.0)
                if should_report_metrics:
                    last_metrics_report_time = now
                    chunk_speech_diag = vad.analyze_speech(audio_samples)
                    metrics_packet = AudioMetricsPacket(
                        sample_rate=sample_rate,
                        samples=sample_count,
                        duration_ms=duration_ms,
                        rms=round(chunk_rms, 4),
                        peak=round(chunk_peak, 4),
                        pipeline_status=pipeline_state,
                        speech_state=chunk_speech_diag["state"],
                    )
                    await websocket.send_text(json.dumps(metrics_packet.model_dump()))

            elif "text" in message and message["text"]:
                try:
                    payload = json.loads(message["text"])
                except Exception as json_err:
                    await websocket.send_text(
                        json.dumps({
                            "type": "protocol_error",
                            "error": f"Malformed JSON control packet: {json_err}",
                        })
                    )
                    continue

                msg_type = payload.get("type") or payload.get("action")

                if msg_type == "start":
                    session_active = True
                    pipeline_state = "WAITING_FOR_AUDIO"
                    if "speaker_id" in payload:
                        active_speaker_id = payload["speaker_id"]
                    if "target_phone" in payload:
                        active_target_phone = payload["target_phone"]
                    if "format" in payload:
                        active_audio_format = payload["format"]
                    buffer.reset()
                    risk_engine.reset()
                    last_metrics_report_time = 0.0
                    await websocket.send_text(
                        json.dumps({
                            "type": "session_started",
                            "session_id": session_id,
                            "speaker_id": active_speaker_id,
                            "format": active_audio_format or "auto",
                            "sample_rate": sample_rate,
                            "pipeline_status": "WAITING_FOR_AUDIO",
                        })
                    )

                elif msg_type == "stop":
                    session_active = False
                    pipeline_state = "READY"
                    buffer.reset()
                    risk_engine.reset()
                    last_metrics_report_time = 0.0
                    # Do NOT close the WebSocket on normal stop
                    await websocket.send_text(
                        json.dumps({
                            "type": "session_stopped",
                            "session_id": session_id,
                            "pipeline_status": "READY",
                            "message": "Live call analysis session stopped.",
                        })
                    )

                elif msg_type == "reset":
                    buffer.reset()
                    risk_engine.reset()
                    last_metrics_report_time = 0.0
                    pipeline_state = "WAITING_FOR_AUDIO" if session_active else "READY"
                    await websocket.send_text(
                        json.dumps({
                            "type": "session_reset",
                            "session_id": session_id,
                            "pipeline_status": pipeline_state,
                            "message": "Audio buffer and risk engine state reset.",
                        })
                    )

                elif msg_type in ("status", "get_status"):
                    await websocket.send_text(
                        json.dumps({
                            "type": "pipeline_status",
                            "status": pipeline_state,
                            "session_id": session_id,
                            "session_active": session_active,
                            "speaker_id": active_speaker_id,
                        })
                    )

                elif msg_type == "switch_speaker" or "speaker_id" in payload:
                    if "speaker_id" in payload:
                        active_speaker_id = payload["speaker_id"]
                    if "target_phone" in payload:
                        active_target_phone = payload["target_phone"]
                    await websocket.send_text(
                        json.dumps({
                            "type": "speaker_switched",
                            "speaker_id": active_speaker_id,
                        })
                    )

                else:
                    await websocket.send_text(
                        json.dumps({
                            "type": "unknown_message",
                            "received_type": str(msg_type),
                        })
                    )

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected cleanly from {endpoint_path} (session={session_id})")
    except Exception as err:
        print(f"[WS Error] Exception in {endpoint_path}: {err}")
    finally:
        buffer.reset()
        risk_engine.reset()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
