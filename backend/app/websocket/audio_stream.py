import os
import json
import time
import traceback
from datetime import datetime
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.audio.protocol import AUDIO_PROTOCOL
from ml.pipeline.multimodel_engine import multimodel_instance
from app.api.speaker_store import get_speaker_embedding

# Robust import for ImpersonationEngine
try:
    from ml.impersonation import ImpersonationEngine
except ImportError:
    import sys
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    from ml.impersonation import ImpersonationEngine

router = APIRouter()

@router.websocket("/ws/analyze")
async def websocket_analyze_endpoint(websocket: WebSocket):
    # 1. ORIGIN VALIDATION (P1-04)
    origin = websocket.headers.get("origin")
    allowed_origins_raw = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175,http://localhost:3000,http://127.0.0.1:3000"
    )
    allowed_origins = [o.strip().rstrip("/") for o in allowed_origins_raw.split(",") if o.strip()]
    
    if origin is not None and "*" not in allowed_origins:
        if origin.rstrip("/") not in allowed_origins:
            # Unauthorized origin: accept then immediately reject with 1008
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "message": f"Unauthorized origin: {origin}"
            })
            await websocket.close(code=1008, reason="Policy Violation: Unauthorized Origin")
            return

    await websocket.accept()
    await websocket.send_json({
        "type": "status",
        "status": "connected",
        "model_status": multimodel_instance.get_status(),
        "production_ready": False,
        "model_disclaimer": "Anti-spoofing model is not validated for production use.",
        "protocol": {
            "sample_rate": AUDIO_PROTOCOL["SAMPLE_RATE"],
            "window_size_samples": AUDIO_PROTOCOL["WINDOW_SIZE_SAMPLES"],
            "hop_size_samples": AUDIO_PROTOCOL["HOP_SIZE_SAMPLES"],
            "max_chunk_bytes": AUDIO_PROTOCOL["MAX_CHUNK_BYTES"],
        }
    })

    # Retrieve cookie token if present
    cookie_token = websocket.cookies.get("vshield_session")
    active_token = cookie_token

    # Per-connection state
    risk_engine = ImpersonationEngine()
    vad = EnergyVAD(energy_threshold=0.005)
    enrolled_embedding = None
    audio_buffer = np.array([], dtype=np.float32)

    # Session State
    session_active = False
    session_start_time = None
    db = None
    user = None
    session_max_risk = 0
    session_max_spoof = 0
    session_min_similarity = 1.0
    session_risk_level = "LOW"
    session_speaker_status = "NOT_ENROLLED"

    try:
        while True:
            message = await websocket.receive()
            frame_recv_time = time.time()

            # A. Control messages (JSON Text)
            if "text" in message and message["text"] is not None:
                try:
                    payload = json.loads(message["text"])
                    msg_type = payload.get("type")

                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
                        continue

                    elif msg_type == "start":
                        risk_engine.reset()

                        # Token lookup order: payload token > cookie token
                        if "token" in payload and payload["token"]:
                            active_token = payload["token"]
                        elif cookie_token:
                            active_token = cookie_token

                        if not active_token:
                            await websocket.send_json({
                                "type": "error",
                                "message": "Authentication required. Provide token in start payload or vshield_session cookie."
                            })
                            await websocket.close(code=1008, reason="Policy Violation: Not authenticated")
                            return

                        from app.api.auth import get_current_user_from_token
                        from app.database.database import SessionLocal
                        from app.database.models import SpeakerProfile

                        if db is None:
                            db = SessionLocal()
                        user = get_current_user_from_token(active_token, db)

                        if not user:
                            if db is not None:
                                db.close()
                                db = None
                            await websocket.send_json({
                                "type": "error",
                                "message": "Invalid or expired authentication token"
                            })
                            await websocket.close(code=1008, reason="Policy Violation: Invalid token")
                            return

                        # Fetch speaker profile if enrolled
                        profile = db.query(SpeakerProfile).filter(SpeakerProfile.user_id == user.id).first()
                        if profile:
                            enrolled_embedding = get_speaker_embedding(profile.id)

                        # Initialize session metrics
                        session_max_risk = 0
                        session_max_spoof = 0
                        session_min_similarity = 1.0
                        session_risk_level = "LOW"
                        session_speaker_status = "NOT_ENROLLED" if enrolled_embedding is None else "MATCH"
                        session_active = True
                        session_start_time = time.time()
                        audio_buffer = np.array([], dtype=np.float32)

                        await websocket.send_json({
                            "type": "status",
                            "status": "authenticated",
                            "user_id": user.id,
                            "email": user.email
                        })

                        await websocket.send_json({
                            "type": "status",
                            "status": "analyzing",
                            "speaker_enrolled": enrolled_embedding is not None,
                            "speaker_status": session_speaker_status,
                            "model_status": multimodel_instance.get_status(),
                            "production_ready": False
                        })

                    elif msg_type == "stop":
                        risk_engine.reset()

                        if session_active and user and db:
                            from app.database.models import AnalysisHistory
                            history = AnalysisHistory(
                                user_id=user.id,
                                timestamp=datetime.utcnow(),
                                risk_score=session_max_risk,
                                risk_level=session_risk_level,
                                spoof_probability=session_max_spoof,
                                speaker_similarity=session_min_similarity if enrolled_embedding is not None else None,
                                speaker_status=session_speaker_status
                            )
                            db.add(history)
                            db.commit()

                        session_active = False
                        session_start_time = None
                        audio_buffer = np.array([], dtype=np.float32)

                        await websocket.send_json({
                            "type": "status",
                            "status": "stopped"
                        })

                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unsupported protocol message type: '{msg_type}'"
                        })

                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Malformed JSON in text frame"
                    })
                continue

            # B. Audio Data (Binary Frames)
            if "bytes" in message and message["bytes"] is not None:
                audio_bytes = message["bytes"]

                # P0-02 SECURITY: Reject binary audio if unauthenticated / session inactive
                if not session_active or user is None:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Authentication required. Active session must be established via 'start' before sending audio frames."
                    })
                    await websocket.close(code=1008, reason="Policy Violation: Unauthenticated audio frame")
                    return

                # P1-05 FRAME LIMITS: Max chunk size check (512 KB)
                if len(audio_bytes) > AUDIO_PROTOCOL["MAX_CHUNK_BYTES"]:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Frame size {len(audio_bytes)} bytes exceeds limit of {AUDIO_PROTOCOL['MAX_CHUNK_BYTES']} bytes"
                    })
                    await websocket.close(code=1009, reason="Message Too Big")
                    return

                if len(audio_bytes) == 0:
                    continue

                # P1-05 FRAME LIMITS: Validate 4-byte Float32 alignment
                if len(audio_bytes) % AUDIO_PROTOCOL["BYTES_PER_SAMPLE"] != 0:
                    await websocket.send_json({
                        "type": "analysis",
                        "status": "error",
                        "error": "Invalid audio chunk byte length: must be multiple of 4 for Float32 PCM"
                    })
                    continue

                # Decode Float32 PCM chunk (16kHz mono)
                try:
                    audio_chunk = np.frombuffer(audio_bytes, dtype=np.float32)
                except Exception as e:
                    await websocket.send_json({
                        "type": "analysis",
                        "status": "error",
                        "error": f"Failed to decode Float32 PCM chunk: {str(e)}"
                    })
                    continue

                # P1-05 FRAME LIMITS: Finite number validation (NaN / Inf protection)
                if not np.all(np.isfinite(audio_chunk)):
                    await websocket.send_json({
                        "type": "analysis",
                        "status": "error",
                        "error": "Audio chunk contains non-finite numeric values (NaN or Inf)"
                    })
                    continue

                # Session timeout guard (1 hour max)
                if session_start_time and (time.time() - session_start_time) > AUDIO_PROTOCOL["MAX_SESSION_SECONDS"]:
                    await websocket.send_json({
                        "type": "status",
                        "status": "timeout",
                        "message": "Maximum session duration exceeded (1 hour)"
                    })
                    await websocket.close(code=1000, reason="Session duration limit exceeded")
                    return

                # VAD Check
                is_speech, rms = vad.is_speech(audio_chunk)
                if not is_speech:
                    await websocket.send_json({
                        "type": "analysis",
                        "status": "silence",
                        "vad": "SILENCE",
                        "rms": float(rms)
                    })
                    continue

                # Append to buffer with memory ceiling protection
                audio_buffer = np.concatenate((audio_buffer, audio_chunk))
                if len(audio_buffer) > AUDIO_PROTOCOL["MAX_BUFFER_SAMPLES"]:
                    audio_buffer = audio_buffer[-AUDIO_PROTOCOL["MAX_BUFFER_SAMPLES"]:]

                # Check if buffer reached 64,000 samples (4.0 seconds)
                if len(audio_buffer) < AUDIO_PROTOCOL["WINDOW_SIZE_SAMPLES"]:
                    await websocket.send_json({
                        "type": "analysis",
                        "status": "buffering",
                        "vad": "SPEECH",
                        "rms": float(rms),
                        "buffer_samples": int(len(audio_buffer)),
                        "buffer_duration_ms": int((len(audio_buffer) / AUDIO_PROTOCOL["SAMPLE_RATE"]) * 1000)
                    })
                    continue

                # We have sufficient audio for full-window inference (64,000 samples)
                inference_chunk = audio_buffer[-AUDIO_PROTOCOL["WINDOW_SIZE_SAMPLES"]:]

                # Retain overlap (1.0s hop size -> keep last 48,000 samples = 3.0s overlap)
                audio_buffer = audio_buffer[-AUDIO_PROTOCOL["OVERLAP_SAMPLES"]:]

                # Run inference
                inf_start = time.time()
                result = multimodel_instance.analyze(inference_chunk, enrolled_embedding)
                inference_ms = result.get("latency", {}).get("total_ms", int((time.time() - inf_start) * 1000))

                if "error" in result:
                    await websocket.send_json({
                        "type": "analysis",
                        "status": "error",
                        "error": result["error"]
                    })
                    continue

                # Stateful Risk Engine
                speaker_similarity = result.get("ecapa", {}).get("speaker_similarity", None)
                spoof_prob = result.get("fusion", {}).get("spoof_probability", 
                                result.get("aasist", {}).get("spoof_probability", 0.5))
                                
                risk_payload = risk_engine.process_window(
                    spoof_probability=spoof_prob,
                    speaker_similarity=speaker_similarity,
                    speaker_enrolled=(enrolled_embedding is not None)
                )

                # Update session metrics
                if session_active:
                    session_max_risk = max(session_max_risk, risk_payload["impersonation_risk_score"])
                    session_max_spoof = max(session_max_spoof, float(spoof_prob))
                    if speaker_similarity is not None:
                        session_min_similarity = min(session_min_similarity, speaker_similarity)
                        if speaker_similarity < 0.25:
                            session_speaker_status = "MISMATCH"

                    if risk_payload["impersonation_risk_level"] in ["CRITICAL", "HIGH"] or (
                        risk_payload["impersonation_risk_level"] == "MEDIUM" and session_risk_level == "LOW"
                    ):
                        session_risk_level = risk_payload["impersonation_risk_level"]

                latency_ms = int((time.time() - frame_recv_time) * 1000)

                # Structured event logging
                print(json.dumps({
                    "event": "inference_success",
                    "user_id": user.id if user else None,
                    "vad": "SPEECH",
                    "rms": float(rms),
                    "inference_ms": inference_ms,
                    "total_latency_ms": latency_ms,
                    "spoof_probability": float(spoof_prob),
                    "model_status": multimodel_instance.get_status(),
                    "impersonation_risk_score": risk_payload["impersonation_risk_score"],
                    "impersonation_risk_level": risk_payload["impersonation_risk_level"]
                }))

                # Send analysis response with explicit model readiness metadata
                await websocket.send_json({
                    "type": "analysis",
                    "status": "success",
                    "timestamp": datetime.utcnow().isoformat(),
                    "window_duration_ms": int(AUDIO_PROTOCOL["WINDOW_SIZE_SECONDS"] * 1000),
                    "vad": "SPEECH",
                    "rms": float(rms),
                    "latency_ms": latency_ms,
                    "inference_ms": inference_ms,
                    "spoof_probability": float(spoof_prob),
                    "model_status": multimodel_instance.get_status(),
                    "production_ready": False,
                    "model_disclaimer": "Anti-spoofing model is not validated for production use.",
                    "speaker_similarity": speaker_similarity,
                    "speaker_status": session_speaker_status,
                    "impersonation_risk_score": risk_payload["impersonation_risk_score"],
                    "impersonation_risk_level": risk_payload["impersonation_risk_level"],
                    "risk_confidence": risk_payload.get("risk_confidence", "HIGH"),
                    "risk_reasons": risk_payload.get("risk_reasons", [])
                })

    except (WebSocketDisconnect, RuntimeError) as e:
        if isinstance(e, RuntimeError) and "disconnect message has been received" not in str(e):
            print(json.dumps({"event": "server_error", "error": str(e), "traceback": traceback.format_exc()}))
            try:
                await websocket.close(code=1011, reason="Internal Error")
            except:
                pass
        else:
            print(json.dumps({"event": "client_disconnected"}))
    except Exception as e:
        print(json.dumps({"event": "server_error", "error": str(e), "traceback": traceback.format_exc()}))
        try:
            await websocket.close(code=1011, reason="Internal Error")
        except:
            pass
    finally:
        # Resource cleanup & failsafe history persistence
        try:
            if session_active and user is not None and db is not None:
                from app.database.models import AnalysisHistory
                history = AnalysisHistory(
                    user_id=user.id,
                    timestamp=datetime.utcnow(),
                    risk_score=session_max_risk,
                    risk_level=session_risk_level,
                    spoof_probability=session_max_spoof,
                    speaker_similarity=session_min_similarity if enrolled_embedding is not None else None,
                    speaker_status=session_speaker_status
                )
                db.add(history)
                db.commit()
        except Exception as e:
            print(f"Error persisting session history on disconnect: {e}")
        finally:
            if db is not None:
                db.close()
                db = None
            audio_buffer = np.array([], dtype=np.float32)
