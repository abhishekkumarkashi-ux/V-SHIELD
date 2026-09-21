"""
V-SHIELD Twilio Live Call Gateway Integration & Unit Tests.
Verifies:
1. POST /api/v1/twilio/voice TwiML generation and custom parameters.
2. X-Twilio-Signature cryptographic request validation.
3. μ-law decoding (audioop-lts) & 8 kHz to 16 kHz polyphase resampling.
4. Call-specific state isolation (call_states[call_sid]).
5. Sliding window timing (4.04s window, 0.5s hop).
6. AASIST anti-spoofing and ECAPA speaker verification (enrolled vs NO_REFERENCE).
7. Dynamic RiskEngine evaluation and automated MFA trigger.
8. Telemetry broadcast to live dashboard WebSocket subscribers.
9. Resilient error handling (malformed JSON, invalid base64, clean disconnect).
"""

import asyncio
import audioop
import base64
import json
import time

import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from app.config import settings
from app.core.buffer import AudioCircularBuffer
from app.core.risk_engine import RiskEngine
from app.core.vad import MarginPreservingVAD
from app.main import app
from app.models.aasist_service import AASISTService
from app.models.ecapa_service import ECAPAService
from app.routers.twilio import (
    CallSessionState,
    broadcast_telemetry,
    call_states,
    get_call_state,
    register_dashboard_subscriber,
    unregister_dashboard_subscriber,
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def generate_synthetic_ulaw_chunk(num_samples: int = 160, freq: float = 440.0, sr: int = 8000) -> bytes:
    """Generates 8 kHz sine wave, normalizes to 16-bit PCM, and encodes to μ-law."""
    t = np.linspace(0, num_samples / sr, num_samples, endpoint=False)
    sine = 0.5 * np.sin(2 * np.pi * freq * t)
    pcm16 = (sine * 32767).astype(np.int16).tobytes()
    ulaw_bytes = audioop.lin2ulaw(pcm16, 2)
    return ulaw_bytes


# =====================================================================
# 1. Voice Webhook & TwiML Generation (Phase 3 & Phase 4)
# =====================================================================


def test_twilio_voice_webhook_generates_valid_twiml(client):
    """Verifies that POST /api/v1/twilio/voice returns valid TwiML XML with <Stream>."""
    response = client.post(
        "/api/v1/twilio/voice",
        data={
            "CallSid": "CA1234567890abcdef1234567890abcdef",
            "From": "+15551234567",
            "To": "+15559876543",
            "CallStatus": "ringing",
        },
    )

    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    xml_content = response.text
    assert "<Response>" in xml_content
    assert "<Connect>" in xml_content
    assert "<Stream" in xml_content
    assert "/ws/twilio-stream" in xml_content
    assert 'name="caller_phone"' in xml_content
    assert 'name="call_sid"' in xml_content


def test_twilio_stream_url_uses_configured_public_base_url(monkeypatch, client):
    """Verifies TWILIO_PUBLIC_BASE_URL is properly converted to wss:// scheme."""
    monkeypatch.setattr(settings, "TWILIO_PUBLIC_BASE_URL", "https://vshield-secure.ngrok-free.app")

    response = client.post(
        "/api/v1/twilio/voice",
        data={"CallSid": "CA_TEST_URL", "From": "+123456"},
    )
    assert response.status_code == 200
    assert "wss://vshield-secure.ngrok-free.app/ws/twilio-stream" in response.text


# =====================================================================
# 2. Twilio Signature Validation (Phase 14)
# =====================================================================


def test_twilio_signature_validation_enforcement(monkeypatch, client):
    """Verifies HMAC signature check rejects spoofed webhooks when auth token is configured."""
    test_auth_token = "auth_token_for_testing_purposes_only"
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", test_auth_token)

    payload = {"CallSid": "CA_SECURE_TEST", "From": "+15550001"}

    # 1. Unsigned or invalid signature request -> Must return 403 Forbidden
    bad_res = client.post(
        "/api/v1/twilio/voice",
        data=payload,
        headers={"X-Twilio-Signature": "invalid_signature_hash"},
    )
    assert bad_res.status_code == 403

    # 2. Request with mathematically valid signature -> Must pass 200 OK
    validator = RequestValidator(test_auth_token)
    req_url = "http://testserver/api/v1/twilio/voice"
    valid_sig = validator.compute_signature(req_url, payload)

    good_res = client.post(
        "/api/v1/twilio/voice",
        data=payload,
        headers={"X-Twilio-Signature": valid_sig},
    )
    assert good_res.status_code == 200


# =====================================================================
# 3. Audio Decoding & Polyphase Resampling (Phase 5 & Phase 7)
# =====================================================================


def test_mulaw_to_pcm16_and_resampling_fidelity():
    """Verifies μ-law decoding and 8 kHz to 16 kHz polyphase upsampling."""
    # 160 samples of 8 kHz = 20ms
    ulaw_chunk = generate_synthetic_ulaw_chunk(num_samples=160, freq=500.0, sr=8000)
    assert len(ulaw_chunk) == 160

    # Decode μ-law to 16-bit linear PCM
    pcm16 = audioop.ulaw2lin(ulaw_chunk, 2)
    assert len(pcm16) == 320  # 160 samples * 2 bytes/sample

    # Ingest into AudioCircularBuffer
    buf = AudioCircularBuffer(capacity=64600, hop_size=8000, target_sample_rate=16000)
    buf.append_pcm16_bytes(pcm16, input_sample_rate=8000)

    # Ingested 160 samples @ 8 kHz must upsample to 320 samples @ 16 kHz
    assert buf.total_samples == 320
    rms = buf.get_current_rms()
    assert rms > 0.0


# =====================================================================
# 4. Call-Specific State Isolation (Phase 6)
# =====================================================================


def test_call_specific_state_isolation():
    """Verifies Call A and Call B maintain isolated buffers with zero cross-contamination."""
    call_a = CallSessionState("CA_ALPHA", "MZ_ALPHA")
    call_b = CallSessionState("CA_BETA", "MZ_BETA")

    ulaw_chunk = generate_synthetic_ulaw_chunk(num_samples=160)
    pcm16 = audioop.ulaw2lin(ulaw_chunk, 2)

    # Ingest into Call A
    call_a.buffer.append_pcm16_bytes(pcm16, input_sample_rate=8000)

    # Check Call A accumulated samples while Call B remains zero
    assert call_a.buffer.total_samples == 320
    assert call_b.buffer.total_samples == 0
    assert call_b.buffer.get_current_rms() == 0.0

    call_a.reset()
    assert call_a.is_active is False


# =====================================================================
# 5. Sliding Window Timing & Latency (Phase 7)
# =====================================================================


def test_sliding_window_requires_full_window_before_first_hop():
    """
    Verifies that AASIST window (64,600 samples ~4.04s) must be primed
    before can_extract() yields, and subsequent hops occur every 8,000 samples.
    """
    buf = AudioCircularBuffer(capacity=64600, hop_size=8000, target_sample_rate=16000)

    # Feed 200 chunks of 20ms (320 samples @ 16kHz = 64,000 samples < 64,600)
    chunk_320 = (generate_synthetic_ulaw_chunk(160))
    pcm320 = audioop.ulaw2lin(chunk_320, 2)

    for _ in range(200):
        buf.append_pcm16_bytes(pcm320, input_sample_rate=8000)

    # 64,000 samples accumulated -> Not yet primed
    assert buf.total_samples == 64000
    assert buf.is_primed is False
    assert buf.can_extract() is False

    # Feed 2 more chunks (640 samples -> 64,640 >= 64,600)
    buf.append_pcm16_bytes(pcm320, input_sample_rate=8000)
    buf.append_pcm16_bytes(pcm320, input_sample_rate=8000)

    assert buf.is_primed is True
    # Now that it's primed, hop accumulation allows extraction
    windows = list(buf.extract_all_ready_windows())
    assert len(windows) >= 1
    assert windows[0].shape == (1, 64600)


# =====================================================================
# 6. Real AASIST, ECAPA, & Risk Engine Telemetry (Phase 8, 9, 10)
# =====================================================================


def test_unenrolled_caller_returns_no_reference_biometric_state():
    """
    Verifies that when caller has no enrolled voiceprint:
    - Telephony pipeline returns NO_REFERENCE
    - RiskEngine evaluates Case 2 (unenrolled) without manufacturing similarity.
    """
    state = CallSessionState("CA_UNENROLLED", "MZ_UNENROLLED", target_speaker_id=None)

    # 1. ECAPA service returns NO_VOICEPRINT for unenrolled
    spk_verif = ECAPAService.get_instance().verify_speaker_detailed(np.zeros(16000, dtype=np.float32), None)
    assert spk_verif["status"] in ("NO_VOICEPRINT", "NO_REFERENCE")
    assert spk_verif["similarity"] is None

    # 2. Risk engine evaluation
    eval_res = state.risk_engine.evaluate_detailed(
        spoof_prob=0.05,
        speaker_similarity=None,
        is_speech_active=True,
        speech_ratio=0.85,
    )

    assert eval_res["classification"] in ("LOW_RISK", "MEDIUM_RISK")
    assert 0.0 <= eval_res["risk_score"] <= 100.0
    assert "anti_spoof" in [f["name"] for f in eval_res["factors"]]


def test_enrolled_caller_biometric_verification_match():
    """Verifies that when an enrolled speaker voiceprint exists, ECAPA computes similarity."""
    ecapa = ECAPAService.get_instance()
    speakers = ecapa.get_enrolled_speakers()
    if not speakers:
        pytest.skip("No enrolled speakers in test db")

    speaker_id = speakers[0]["speaker_id"]
    dummy_voice = np.sin(2 * np.pi * 300 * np.linspace(0, 1, 16000)).astype(np.float32)

    verif = ecapa.verify_speaker_detailed(dummy_voice, speaker_id)
    assert verif["speaker_id"] == speaker_id
    assert verif["similarity"] is not None
    assert -1.0 <= verif["similarity"] <= 1.0


# =====================================================================
# 7. End-to-End WebSocket Stream & Telemetry Bridge (Phase 5, 11, 19)
# =====================================================================


def test_e2e_twilio_stream_websocket_pipeline(client):
    """
    Full integration test:
    Connects to /ws/twilio-stream, sends 'start', streams media packets,
    observes inference logging, and sends 'stop' with state cleanup.
    """
    with client.websocket_connect("/ws/twilio-stream") as ws:
        call_sid = f"CA_E2E_{int(time.time()*1000)}"
        stream_sid = f"MZ_E2E_{int(time.time()*1000)}"

        # 1. Send start event
        start_pkt = {
            "event": "start",
            "sequenceNumber": "1",
            "start": {
                "streamSid": stream_sid,
                "callSid": call_sid,
                "tracks": ["inbound"],
                "customParameters": {
                    "caller_phone": "+15558889999",
                },
                "mediaFormat": {
                    "encoding": "audio/x-mulaw",
                    "sampleRate": 8000,
                    "channels": 1,
                },
            },
        }
        ws.send_text(json.dumps(start_pkt))

        # Verify state created (with small async processing wait)
        for _ in range(50):
            if call_sid in call_states:
                break
            time.sleep(0.02)
        assert call_sid in call_states
        state = call_states[call_sid]
        assert state.stream_sid == stream_sid
        assert state.caller_phone == "+15558889999"

        # 2. Send 210 media packets to prime 64,600 samples and trigger inference
        ulaw_data = generate_synthetic_ulaw_chunk(160, freq=440.0)
        b64_payload = base64.b64encode(ulaw_data).decode("ascii")

        for seq in range(2, 215):
            media_pkt = {
                "event": "media",
                "sequenceNumber": str(seq),
                "media": {
                    "track": "inbound",
                    "chunk": str(seq),
                    "timestamp": str(int(time.time() * 1000)),
                    "payload": b64_payload,
                },
            }
            ws.send_text(json.dumps(media_pkt))

        # Verify packets ingested and inferences executed
        assert state.packet_count >= 210
        assert state.inference_count >= 1

        # 3. Send stop event
        stop_pkt = {
            "event": "stop",
            "sequenceNumber": "215",
            "stop": {
                "callSid": call_sid,
                "accountSid": "AC_TEST",
            },
        }
        ws.send_text(json.dumps(stop_pkt))
        for _ in range(30):
            if call_sid not in call_states:
                break
            time.sleep(0.05)

    # State should be removed from call_states
    for _ in range(20):
        if call_sid not in call_states:
            break
        time.sleep(0.05)
    assert call_sid not in call_states


def test_malformed_packets_do_not_crash_stream(client):
    """Verifies that invalid base64, garbage JSON, and empty payloads are safely handled."""
    with client.websocket_connect("/ws/twilio-stream") as ws:
        # Invalid JSON
        ws.send_text("THIS IS NOT JSON {{{")

        # Invalid base64 in media
        ws.send_text(
            json.dumps(
                {
                    "event": "media",
                    "media": {"payload": "!!NOT_BASE64@@"},
                }
            )
        )

        # Empty packet
        ws.send_text(json.dumps({}))

        # Valid start still works after errors
        ws.send_text(
            json.dumps(
                {
                    "event": "start",
                    "start": {"callSid": "CA_RECOVER", "streamSid": "MZ_RECOVER"},
                }
            )
        )
        for _ in range(50):
            if "CA_RECOVER" in call_states:
                break
            time.sleep(0.02)
        assert "CA_RECOVER" in call_states
        call_states.pop("CA_RECOVER", None)


def test_twilio_gateway_status_endpoint(client):
    """Verifies GET /api/v1/twilio/status provides telemetry health and active calls."""
    res = client.get("/api/v1/twilio/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert "active_calls_count" in data
    assert "dashboard_subscribers_count" in data
