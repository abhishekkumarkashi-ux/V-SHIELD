from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import time
import numpy as np
import traceback

from app.ml.model import model_instance
from app.ml.vad import EnergyVAD
from app.api.speaker_store import get_speaker_embedding
from app.ml.speaker_verification import speaker_verification_instance

router = APIRouter()

@router.websocket("/ws/analyze")
async def websocket_analyze_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Simple WebSocket Authentication
    # Check cookies for vshield_session
    token = websocket.cookies.get("vshield_session")
    
    # We'll wait for the "start" message to verify token if not in cookies
    # or just proceed and verify when we get the "start" message.
    
    # 1. Instantiate per-connection state
    # We dynamically import ImpersonationEngine because sys.path is appended in model.py
    try:
        from ml.impersonation import ImpersonationEngine
        risk_engine = ImpersonationEngine()
    except ImportError as e:
        print(f"Error importing ImpersonationEngine: {e}")
        await websocket.close(code=1011, reason="Internal Server Error: Risk Engine missing")
        return

    vad = EnergyVAD(energy_threshold=0.005) # Configurable
    enrolled_embedding = None

    try:
        while True:
            # Receive any frame (text or binary)
            message = await websocket.receive()
            start_time = time.time()
            
            # Control messages (JSON Text)
            if "text" in message and message["text"] is not None:
                try:
                    payload = json.loads(message["text"])
                    if payload.get("type") == "start":
                        risk_engine.reset()
                        
                        # Check auth in payload if not in cookie
                        if not token and "token" in payload:
                            token = payload["token"]
                            
                        if not token:
                            await websocket.send_json({"type": "error", "message": "Authentication required"})
                            await websocket.close(code=1008, reason="Policy Violation: Not authenticated")
                            return
                            
                        from app.api.auth import get_current_user_from_token
                        from app.database.database import SessionLocal
                        
                        db = SessionLocal()
                        user = get_current_user_from_token(token, db)
                        db.close()
                        
                        if not user:
                            await websocket.send_json({"type": "error", "message": "Invalid authentication token"})
                            await websocket.close(code=1008, reason="Policy Violation: Invalid token")
                            return
                        
                        print(f"WebSocket auth successful for user {user.id}")
                        
                        speaker_id = payload.get("speaker_id")
                        if speaker_id:
                            enrolled_embedding = get_speaker_embedding(speaker_id)
                            
                        await websocket.send_json({
                            "type": "status",
                            "status": "connected",
                            "speaker_enrolled": enrolled_embedding is not None
                        })
                    elif data.get("type") == "stop":
                        risk_engine.reset()
                        await websocket.send_json({
                            "type": "status",
                            "status": "stopped"
                        })
                except json.JSONDecodeError:
                    pass
                continue
                
            # Audio Data (Binary)
            if "bytes" in message and message["bytes"] is not None:
                audio_bytes = message["bytes"]
                
                # SECURITY: Max chunk size limit (512KB max to prevent memory exhaustion)
                if len(audio_bytes) > 512 * 1024:
                    print(f"SECURITY: Disconnecting client. Chunk size {len(audio_bytes)} exceeds 512KB limit.")
                    await websocket.close(code=1009, reason="Message Too Big")
                    break
                    
                if len(audio_bytes) == 0:
                    continue
                    
                # Decode Float32 PCM chunk (16kHz mono)
                try:
                    audio_chunk = np.frombuffer(audio_bytes, dtype=np.float32)
                except Exception:
                    await websocket.send_json({
                        "type": "analysis",
                        "status": "error",
                        "error": "Invalid audio chunk format"
                    })
                    continue
                
                # VAD Check
                if not vad.is_speech(audio_chunk):
                    # Structured Log
                    print(json.dumps({
                        "event": "inference_skip",
                        "vad": "SILENCE",
                        "processing_ms": int((time.time() - start_time) * 1000)
                    }))
                    await websocket.send_json({
                        "type": "analysis",
                        "status": "silence",
                        "vad": "SILENCE"
                    })
                    continue
                
                # Inference
                inf_start = time.time()
                result = model_instance.predict_pcm(audio_chunk)
                inference_ms = int((time.time() - inf_start) * 1000)
                
                if "error" in result:
                    await websocket.send_json({
                        "type": "analysis",
                        "status": "error",
                        "error": "Internal inference error" # Do not leak raw errors
                    })
                    continue
                    
                # Speaker Verification
                speaker_similarity = None
                if enrolled_embedding is not None:
                    chunk_emb_res = speaker_verification_instance.extract_embedding(audio_chunk)
                    if "embedding" in chunk_emb_res:
                        speaker_similarity = speaker_verification_instance.compute_similarity(
                            enrolled_embedding, chunk_emb_res["embedding"]
                        )
                    
                # Calculate risk score with stateful engine
                risk_payload = risk_engine.process_window(
                    spoof_probability=result["spoof_probability"], 
                    speaker_similarity=speaker_similarity,
                    speaker_enrolled=(enrolled_embedding is not None)
                )
                
                # Performance metrics
                latency_ms = int((time.time() - start_time) * 1000)
                
                # Structured Logging
                print(json.dumps({
                    "event": "inference_success",
                    "vad": "SPEECH",
                    "inference_ms": inference_ms,
                    "total_latency_ms": latency_ms,
                    "spoof_probability": float(result["spoof_probability"]),
                    "impersonation_risk_score": risk_payload["impersonation_risk_score"],
                    "impersonation_risk_level": risk_payload["impersonation_risk_level"]
                }))
                
                await websocket.send_json({
                    "type": "analysis",
                    "status": "success",
                    "vad": "SPEECH",
                    "latency_ms": latency_ms,
                    **risk_payload
                })
                
    except WebSocketDisconnect:
        print(json.dumps({"event": "client_disconnected"}))
    except Exception as e:
        # Avoid leaking full stack trace
        print(json.dumps({"event": "server_error", "error": str(e)}))
        try:
            await websocket.close(code=1011, reason="Internal Error")
        except:
            pass
