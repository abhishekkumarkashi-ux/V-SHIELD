"""
V-SHIELD Twilio Inbound Telephony Gateway Router (SIH 2026).
Handles:
1. POST /api/v1/twilio/voice: Inbound Voice Webhook returning TwiML with <Connect><Stream>.
2. WS /ws/twilio-stream: Real-Time Twilio Media Stream WebSocket (8 kHz μ-law -> PCM16 -> 16 kHz).
3. Call-specific isolated state machine (call_states[call_sid]).
4. End-to-end integration: Buffer -> VAD -> AASIST -> ECAPA -> RiskEngine -> Live Telemetry.
"""

import asyncio
import audioop
import base64
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Connect, Stream, VoiceResponse

from app.config import settings
from app.core.buffer import AudioCircularBuffer
from app.core.mfa_service import MFAService
from app.core.risk_engine import RiskEngine
from app.core.vad import MarginPreservingVAD
from app.models.aasist_service import AASISTService
from app.models.ecapa_service import ECAPAService

logger = logging.getLogger("vshield.twilio")

router = APIRouter(prefix="/twilio", tags=["Twilio Live Call Gateway"])

# Global singletons
aasist_service = AASISTService.get_instance()
ecapa_service = ECAPAService.get_instance()
mfa_service = MFAService.get_instance()

# Active Dashboard Telemetry Subscribers
_dashboard_subscribers: Set[WebSocket] = set()
_subscribers_lock = asyncio.Lock()


async def register_dashboard_subscriber(ws: WebSocket) -> None:
    """Registers an active dashboard WebSocket to receive telephony telemetry."""
    async with _subscribers_lock:
        _dashboard_subscribers.add(ws)


async def unregister_dashboard_subscriber(ws: WebSocket) -> None:
    """Unregisters a dashboard WebSocket."""
    async with _subscribers_lock:
        _dashboard_subscribers.discard(ws)


async def broadcast_telemetry(payload: Dict[str, Any]) -> None:
    """Safely broadcasts telemetry updates to all active dashboard subscribers."""
    dead_sockets: List[WebSocket] = []
    message_text = json.dumps(payload)

    async with _subscribers_lock:
        targets = list(_dashboard_subscribers)

    for client in targets:
        try:
            await client.send_text(message_text)
        except Exception:
            dead_sockets.append(client)

    if dead_sockets:
        async with _subscribers_lock:
            for dead in dead_sockets:
                _dashboard_subscribers.discard(dead)


# =====================================================================
# Call-Specific State Isolation (Phase 6)
# =====================================================================


class CallSessionState:
    """
    Encapsulates isolated state for an active telephone call.
    Guarantees zero memory bleeding or audio contamination across concurrent calls.
    """

    def __init__(
        self,
        call_sid: str,
        stream_sid: str,
        caller_phone: Optional[str] = None,
        target_speaker_id: Optional[str] = None,
    ) -> None:
        self.call_sid: str = call_sid
        self.stream_sid: str = stream_sid
        self.caller_phone: Optional[str] = caller_phone
        self.target_speaker_id: Optional[str] = target_speaker_id

        # Isolated audio buffer: 64,600 capacity (~4.04s @ 16kHz), 8,000 hop (~0.5s)
        self.buffer: AudioCircularBuffer = AudioCircularBuffer(
            capacity=settings.WINDOW_SIZE,
            hop_size=settings.HOP_SIZE,
            target_sample_rate=settings.SAMPLE_RATE,
        )

        # Isolated VAD & Risk Engine
        self.vad: MarginPreservingVAD = MarginPreservingVAD(
            sample_rate=settings.SAMPLE_RATE,
            min_silence_padding_sec=settings.VAD_MARGIN_SEC,
        )
        self.risk_engine: RiskEngine = RiskEngine(alpha=settings.RISK_ALPHA)

        # Telemetry and diagnostics
        self.created_at: float = time.time()
        self.last_media_time: float = time.time()
        self.packet_count: int = 0
        self.inference_count: int = 0
        self.latest_risk_score: float = 0.0
        self.latest_classification: str = "INSUFFICIENT_DATA"
        self.is_active: bool = True

    def reset(self) -> None:
        """Purges buffered audio and resets state."""
        self.buffer.reset()
        self.risk_engine.reset()
        self.is_active = False


# Active Call Registry
call_states: Dict[str, CallSessionState] = {}


def get_call_state(call_sid: str) -> Optional[CallSessionState]:
    """Retrieves session state for a given Call SID."""
    return call_states.get(call_sid)


# =====================================================================
# Helper: Public WSS Stream URL Construction (Phase 4)
# =====================================================================


def build_stream_url(request: Request) -> str:
    """
    Constructs the secure WebSocket URL (wss://...) for Twilio Media Streams.
    Prioritizes TWILIO_PUBLIC_BASE_URL environment variable; falls back to request Host.
    """
    base_url = settings.TWILIO_PUBLIC_BASE_URL
    if base_url and base_url.strip():
        base = base_url.strip().rstrip("/")
        if base.startswith("https://"):
            ws_base = "wss://" + base[8:]
        elif base.startswith("http://"):
            ws_base = "ws://" + base[7:]
        elif base.startswith("wss://") or base.startswith("ws://"):
            ws_base = base
        else:
            ws_base = f"wss://{base}"
        return f"{ws_base}/ws/twilio-stream"

    # Fallback from request URL
    host = request.headers.get("host") or f"{request.url.hostname}:{request.url.port}"
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    ws_scheme = "wss" if proto == "https" else "ws"
    return f"{ws_scheme}://{host}/ws/twilio-stream"


# =====================================================================
# Phase 4 & Phase 14: Twilio Voice Webhook & Security Validation
# =====================================================================


@router.post("/voice")
async def twilio_voice_webhook(
    request: Request,
    x_twilio_signature: Optional[str] = Header(None, alias="X-Twilio-Signature"),
) -> Response:
    """
    Twilio Inbound Voice Webhook.
    Validates Twilio request signature if TWILIO_AUTH_TOKEN is configured.
    Returns valid TwiML directing Twilio to stream real-time audio over WebSocket.
    """
    form_data = await request.form()
    params = dict(form_data)

    call_sid = params.get("CallSid", "UNKNOWN")
    from_phone = params.get("From", "UNKNOWN")
    to_phone = params.get("To", "UNKNOWN")

    logger.info(
        f"[TWILIO] Incoming call received: CallSid={call_sid}, From={from_phone}, To={to_phone}"
    )
    print(f"[TWILIO] call started: CallSid={call_sid} From={from_phone} To={to_phone}")

    # Twilio Request Signature Validation (Phase 14)
    if settings.TWILIO_AUTH_TOKEN and settings.TWILIO_AUTH_TOKEN.strip():
        validator = RequestValidator(settings.TWILIO_AUTH_TOKEN.strip())
        full_url = str(request.url)
        # Check signature against request URL and POST parameters
        is_valid = validator.validate(full_url, params, x_twilio_signature or "")
        if not is_valid:
            logger.warning(
                f"[TWILIO Security] Rejected unauthorized webhook call: CallSid={call_sid}"
            )
            raise HTTPException(status_code=403, detail="Twilio signature validation failed.")

    # Generate TwiML response instructing Twilio to stream audio to /ws/twilio-stream
    stream_url = build_stream_url(request)
    logger.info(f"[TWILIO] Connecting Media Stream to {stream_url}")

    response = VoiceResponse()
    connect = Connect()
    stream = Stream(url=stream_url)
    # Pass caller phone and CallSid as custom stream parameters
    stream.parameter(name="caller_phone", value=from_phone)
    stream.parameter(name="call_sid", value=call_sid)
    connect.append(stream)
    response.append(connect)

    twiml_xml = str(response)
    return Response(content=twiml_xml, media_type="application/xml")


# =====================================================================
# Phase 5: Twilio Media Stream WebSocket (/ws/twilio-stream)
# =====================================================================


async def handle_twilio_stream_session(websocket: WebSocket) -> None:
    """
    Core Twilio Media Stream WebSocket worker.
    Processes:
    - 'start': Initializes CallSessionState.
    - 'media': Decodes μ-law 8kHz -> PCM16 -> 16kHz -> feeds sliding buffer -> runs models on hop -> broadcasts telemetry.
    - 'stop': Cleans up call state and audio buffers.
    """
    await websocket.accept()
    logger.info("[TWILIO] Media Stream WebSocket connected")

    current_call_sid: Optional[str] = None
    current_stream_sid: Optional[str] = None

    try:
        while True:
            message_text = await websocket.receive_text()
            if not message_text:
                continue

            try:
                msg = json.loads(message_text)
            except Exception as parse_err:
                logger.warning(f"[TWILIO Error] Malformed JSON in stream: {parse_err}")
                continue

            event_type = msg.get("event")

            # -------------------------------------------------------------
            # Event: start
            # -------------------------------------------------------------
            if event_type == "start":
                start_data = msg.get("start", {})
                current_stream_sid = start_data.get("streamSid") or msg.get(
                    "streamSid", "UNKNOWN_STREAM"
                )
                current_call_sid = start_data.get("callSid") or msg.get(
                    "callSid", f"call_{int(time.time()*1000)}"
                )

                custom_params = start_data.get("customParameters", {})
                caller_phone = custom_params.get("caller_phone") or custom_params.get("From")
                target_speaker_id = custom_params.get("speaker_id")

                # Initialize Call-Specific State
                state = CallSessionState(
                    call_sid=current_call_sid,
                    stream_sid=current_stream_sid,
                    caller_phone=caller_phone,
                    target_speaker_id=target_speaker_id,
                )
                call_states[current_call_sid] = state

                logger.info(
                    f"[TWILIO] stream started: call_sid={current_call_sid} stream_sid={current_stream_sid}"
                )
                print(
                    f"[TWILIO] stream started: call_sid={current_call_sid} stream_sid={current_stream_sid}"
                )

                # Broadcast Call Started event to dashboard
                await broadcast_telemetry(
                    {
                        "type": "twilio_call_started",
                        "call_sid": current_call_sid,
                        "stream_sid": current_stream_sid,
                        "caller_phone": caller_phone,
                        "speaker_id": target_speaker_id,
                        "timestamp": time.time(),
                        "gateway_status": "STREAMING",
                    }
                )

            # -------------------------------------------------------------
            # Event: media
            # -------------------------------------------------------------
            elif event_type == "media":
                media_data = msg.get("media", {})
                payload_b64 = media_data.get("payload")
                if not payload_b64:
                    continue

                if not current_call_sid or current_call_sid not in call_states:
                    # In case media arrives before start packet, generate fallback key
                    current_stream_sid = msg.get("streamSid", "UNKNOWN_STREAM")
                    current_call_sid = f"fallback_{current_stream_sid}"
                    call_states[current_call_sid] = CallSessionState(
                        call_sid=current_call_sid,
                        stream_sid=current_stream_sid,
                    )

                state = call_states[current_call_sid]
                state.packet_count += 1
                state.last_media_time = time.time()

                # Phase 5 Audio Pipeline:
                # 1. Base64 Decode
                try:
                    raw_ulaw = base64.b64decode(payload_b64)
                except Exception as b64_err:
                    logger.warning(f"[AUDIO Error] Base64 decode failed: {b64_err}")
                    continue

                # 2. Decode 8 kHz μ-law -> Linear 16-bit PCM (2 bytes/sample)
                try:
                    pcm16_bytes = audioop.ulaw2lin(raw_ulaw, 2)
                except Exception as ulaw_err:
                    logger.warning(f"[AUDIO Error] μ-law decoding failed: {ulaw_err}")
                    continue

                # 3. Ingest PCM16 into call-specific buffer with 8 kHz -> 16 kHz polyphase upsampling
                try:
                    state.buffer.append_pcm16_bytes(pcm16_bytes, input_sample_rate=8000)
                except Exception as buf_err:
                    logger.warning(f"[AUDIO Error] Buffer ingestion failed: {buf_err}")
                    continue

                # 4. Check sliding window readiness (AASIST requires 64,600 samples ~4.04s)
                for window_tensor in state.buffer.extract_all_ready_windows():
                    state.inference_count += 1
                    t_hop_start = time.perf_counter()

                    try:
                        # 4a. Margin-Preserving Voice Activity Detection (Phase 7)
                        t_vad_start = time.perf_counter()
                        is_speech_active, speech_ratio, safe_audio = state.vad.process_window(
                            window_tensor
                        )
                        audio_buffer_ms = round((time.perf_counter() - t_vad_start) * 1000.0, 2)

                        # 4b & 4c. Parallel Model Inference: AASIST Anti-Spoofing & ECAPA Biometrics (Rule 11)
                        t_inf_start = time.perf_counter()
                        target_spk = state.target_speaker_id
                        if target_spk:
                            aasist_res, spk_verif = await asyncio.gather(
                                asyncio.to_thread(aasist_service.predict, safe_audio),
                                asyncio.to_thread(
                                    ecapa_service.verify_speaker_detailed, safe_audio, target_spk
                                ),
                            )
                            t_inf_end = time.perf_counter()
                            _, spoof_prob = aasist_res
                            inference_ms = round((t_inf_end - t_inf_start) * 1000.0, 2)
                            speaker_verification_ms = inference_ms
                            speaker_similarity = spk_verif["similarity"]
                            speaker_status = spk_verif["status"]
                        else:
                            aasist_res = await asyncio.to_thread(aasist_service.predict, safe_audio)
                            t_inf_end = time.perf_counter()
                            _, spoof_prob = aasist_res
                            inference_ms = round((t_inf_end - t_inf_start) * 1000.0, 2)
                            speaker_verification_ms = 0.0
                            speaker_similarity = None
                            speaker_status = "NO_REFERENCE"
                            spk_verif = {
                                "status": "NO_REFERENCE",
                                "similarity": None,
                                "speaker_id": None,
                                "is_match": False,
                                "has_voiceprint": False,
                            }

                        # 4d. Authoritative Multi-Signal Risk Engine Evaluation (Phase 10)
                        risk_eval = state.risk_engine.evaluate_detailed(
                            spoof_prob=spoof_prob,
                            speaker_similarity=speaker_similarity,
                            is_speech_active=is_speech_active,
                            speech_ratio=speech_ratio,
                        )
                        risk_score = risk_eval["risk_score"]
                        classification = risk_eval["classification"]
                        recommended_action = risk_eval["recommended_action"]

                        state.latest_risk_score = risk_score
                        state.latest_classification = classification

                        # 4e. Automated Out-of-Band MFA Trigger (Phase 10)
                        mfa_status = "NONE"
                        target_phone = state.caller_phone or settings.DEFAULT_MFA_TARGET_PHONE
                        if RiskEngine.should_trigger_mfa(risk_score, recommended_action):
                            mfa_res = await mfa_service.dispatch_mfa_challenge(
                                target_id=state.call_sid,
                                phone_number=target_phone,
                            )
                            res_status = mfa_res.get("status")
                            if res_status == "dispatched":
                                mfa_status = "DISPATCHED"
                            elif res_status == "cooldown_active":
                                mfa_status = "COOLDOWN"

                        # Latency breakdown
                        total_hop_ms = round((time.perf_counter() - t_hop_start) * 1000.0, 2)
                        latency_breakdown = {
                            "audio_buffer_ms": audio_buffer_ms,
                            "inference_ms": inference_ms,
                            "speaker_verification_ms": speaker_verification_ms,
                            "total_ms": total_hop_ms,
                        }

                        # 4f. Broadcast Structured Telemetry Packet (Phase 11)
                        rms_energy = state.buffer.get_current_rms()
                        telemetry_packet = {
                            "type": "telemetry",
                            "source": "twilio_pstn",
                            "call_sid": state.call_sid,
                            "stream_sid": state.stream_sid,
                            "caller_phone": state.caller_phone,
                            "timestamp": time.time(),
                            "risk_score": round(risk_score, 2),
                            "classification": classification,
                            "decision": risk_eval["decision"],
                            "factors": risk_eval["factors"],
                            "metrics": {
                                "spoof_probability": round(spoof_prob, 4),
                                "speaker_similarity": (
                                    round(speaker_similarity, 4)
                                    if speaker_similarity is not None
                                    else None
                                ),
                                "speaker_status": speaker_status,
                                "buffer_energy_rms": round(rms_energy, 4),
                                "vad_speech_ratio": round(speech_ratio, 4),
                                "latency_ms": total_hop_ms,
                            },
                            "speaker_verification_status": speaker_status,
                            "recommended_action": recommended_action,
                            "mfa_status": mfa_status,
                            "status": "success",
                            "pipeline_status": "ANALYZING",
                            "speaker": {
                                "status": speaker_status,
                                "similarity": (
                                    round(speaker_similarity, 4)
                                    if speaker_similarity is not None
                                    else None
                                ),
                                "speaker_id": target_spk,
                                "is_match": spk_verif.get("is_match", False),
                                "has_voiceprint": spk_verif.get("has_voiceprint", False),
                            },
                            "latency": latency_breakdown,
                        }

                        print(
                            f"[TWILIO INFERENCE] CallSid={state.call_sid} "
                            f"Risk={risk_score:.1f} P(spoof)={spoof_prob:.4f} "
                            f"Sim={speaker_similarity} Action={recommended_action} "
                            f"Latency={total_hop_ms}ms"
                        )
                        await broadcast_telemetry(telemetry_packet)

                    except Exception as model_err:
                        logger.error(
                            f"[TWILIO ML Error] Inference failure for {state.call_sid}: {model_err}"
                        )

            # -------------------------------------------------------------
            # Event: stop
            # -------------------------------------------------------------
            elif event_type == "stop":
                stop_data = msg.get("stop", {})
                stopped_call_sid = stop_data.get("callSid") or current_call_sid

                logger.info(f"[TWILIO] call stopped: call_sid={stopped_call_sid}")
                print(f"[TWILIO] call stopped: call_sid={stopped_call_sid}")

                if stopped_call_sid and stopped_call_sid in call_states:
                    st = call_states.pop(stopped_call_sid)
                    st.reset()
                    print(f"[TWILIO] state cleaned: call_sid={stopped_call_sid}")

                # Broadcast Call Stopped to dashboard
                await broadcast_telemetry(
                    {
                        "type": "twilio_call_stopped",
                        "call_sid": stopped_call_sid,
                        "timestamp": time.time(),
                        "gateway_status": "DISCONNECTED",
                    }
                )

    except WebSocketDisconnect:
        logger.info(f"[TWILIO] Stream client disconnected cleanly: call_sid={current_call_sid}")
        print(f"[TWILIO] Stream client disconnected: call_sid={current_call_sid}")
    except Exception as stream_err:
        logger.error(f"[TWILIO Error] Stream socket exception: {stream_err}")
    finally:
        # Guaranteed cleanup on disconnection
        if current_call_sid and current_call_sid in call_states:
            st = call_states.pop(current_call_sid, None)
            if st:
                st.reset()
            print(f"[TWILIO] state cleaned on disconnect: call_sid={current_call_sid}")


# Mount WebSocket directly on router and export handler
@router.websocket("/stream")
async def twilio_stream_router_endpoint(websocket: WebSocket):
    await handle_twilio_stream_session(websocket)


# =====================================================================
# Telephony Diagnostic Endpoints
# =====================================================================


@router.get("/status")
async def twilio_gateway_status() -> Dict[str, Any]:
    """Returns real-time gateway readiness, active phone calls, and subscriber counts."""
    return {
        "status": "ready",
        "active_calls_count": len(call_states),
        "active_calls": [
            {
                "call_sid": cs.call_sid,
                "stream_sid": cs.stream_sid,
                "caller_phone": cs.caller_phone,
                "packets": cs.packet_count,
                "inferences": cs.inference_count,
                "latest_risk": round(cs.latest_risk_score, 2),
                "uptime_sec": round(time.time() - cs.created_at, 1),
            }
            for cs in call_states.values()
        ],
        "dashboard_subscribers_count": len(_dashboard_subscribers),
        "public_base_url": settings.TWILIO_PUBLIC_BASE_URL,
    }
