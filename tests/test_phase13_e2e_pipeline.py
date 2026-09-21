"""
Phase 13: End-to-End Automated Integration Test Suite for V-SHIELD Live Pipeline.
Covers:
TEST 1  — HEALTH: GET /health returns HTTP 200 and truthful runtime state.
TEST 2  — MODEL STATUS: Truthful model_loaded, device, and service status.
TEST 3  — WEBSOCKET CONNECTION: Authenticated user connects successfully.
TEST 4  — UNAUTHENTICATED WEBSOCKET: Rejection / explicit auth error (UNAUTHORIZED).
TEST 5  — START SESSION: {"type": "start"} returns {"type": "session_started"}.
TEST 6  — INVALID AUDIO: Malformed binary handled safely without crash.
TEST 7  — VALID FLOAT32 PCM: Valid PCM accepted; sample count, RMS, peak, sample rate verified.
TEST 8  — SILENCE: Pure zero PCM yields SILENCE, suppresses false genuine inference.
TEST 9  — SPEECH-LIKE AUDIO: Modulated signal transitions VAD to speech.
TEST 10 — INFERENCE: Valid inference window invokes anti-spoof model.
TEST 11 — ECAPA: Voiceprint enrolled -> comparison called; unenrolled -> NO_VOICEPRINT (not MISMATCH).
TEST 12 — RISK ENGINE: Real signals drive dynamic risk; no hardcoded 0 or 100; insufficient evidence handled.
TEST 13 — STOP: {"type": "stop"} returns {"type": "session_stopped"} without crash.
TEST 14 — POST-STOP AUDIO: Audio sent after stop returns SESSION_NOT_ACTIVE.
TEST 15 — DISCONNECT: Disconnection cleanly cleans up buffers and session state without exceptions.
"""

import json
from unittest.mock import patch

import numpy as np
import pytest
from app.config import settings
from app.core.auth import get_default_operator_token
from app.main import aasist_service, app, ecapa_service
from fastapi.testclient import TestClient

client = TestClient(app)
AUTH_TOKEN = get_default_operator_token()


# =====================================================================
# TEST 1 — HEALTH
# =====================================================================
def test_01_health():
    """GET /health must return HTTP 200 and truthful runtime state."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded", "error", "ONLINE")
    assert "model_loaded" in data
    assert isinstance(data["model_loaded"], bool)
    assert data["version"] == settings.VERSION


# =====================================================================
# TEST 2 — MODEL STATUS
# =====================================================================
def test_02_model_status():
    """Verify model_loaded, device, anti-spoof status, speaker verification status without fake values."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()

    # Verify anti-spoof model status matches reality
    assert data["model_loaded"] == bool(aasist_service.is_loaded or aasist_service.is_onnx_loaded)
    assert "anti_spoof_model" in data
    assert "AASIST" in data["anti_spoof_model"]

    # Verify device
    assert "device" in data
    assert data["device"] in ("cuda", "cpu")

    # Verify speaker verification status
    assert "speaker_verification_loaded" in data
    expected_spk = bool(ecapa_service.is_loaded or ecapa_service.is_onnx_loaded)
    assert data["speaker_verification_loaded"] == expected_spk
    assert data["enrolled_speakers_count"] >= 0


# =====================================================================
# TEST 3 — WEBSOCKET CONNECTION
# =====================================================================
def test_03_websocket_connection():
    """Authenticated user connects successfully to live WebSocket."""
    with client.websocket_connect(f"/ws/analyze?token={AUTH_TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "get_status"}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "pipeline_status"
        assert resp["status"] == "READY"
        assert "session_id" in resp


# =====================================================================
# TEST 4 — UNAUTHENTICATED WEBSOCKET
# =====================================================================
def test_04_unauthenticated_websocket():
    """Unauthenticated client is rejected with explicit auth error."""
    with client.websocket_connect("/ws/analyze") as ws:
        # Attempt to issue command without authentication
        ws.send_text(json.dumps({"type": "start", "speaker_id": "exec-001"}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "auth_error"
        assert resp["code"] in ("UNAUTHORIZED", "UNAUTHENTICATED")
        assert "Authentication required" in resp["message"]


# =====================================================================
# TEST 5 — START SESSION
# =====================================================================
def test_05_start_session():
    """Send {"type": "start"} returns {"type": "session_started"}."""
    with client.websocket_connect(f"/ws/analyze?token={AUTH_TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "start", "speaker_id": "exec-001", "format": "float32"}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "session_started"
        assert resp["speaker_id"] == "exec-001"
        assert resp["pipeline_status"] == "WAITING_FOR_AUDIO"
        assert "session_id" in resp


# =====================================================================
# TEST 6 — INVALID AUDIO
# =====================================================================
def test_06_invalid_audio():
    """Send malformed binary data returns controlled audio error without crashing backend."""
    with client.websocket_connect(f"/ws/analyze?token={AUTH_TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        # 1. Packet too small (< 4 bytes)
        ws.send_bytes(b"\x00\x01")
        err1 = json.loads(ws.receive_text())
        assert err1["type"] == "audio_error"
        assert "too small" in err1["error"]

        # 2. Non-divisible by 4 for float32
        ws.send_bytes(b"\x00" * 7)
        err2 = json.loads(ws.receive_text())
        assert err2["type"] == "audio_error"
        assert "not divisible by 4" in err2["error"]

        # 3. NaNs and Infs in float32 stream
        nan_audio = np.array([0.0, np.nan, np.inf, 0.5], dtype=np.float32)
        ws.send_bytes(nan_audio.tobytes())
        err3 = json.loads(ws.receive_text())
        assert err3["type"] == "audio_error"
        assert "Non-finite" in err3["error"]

        # 4. Verify socket is still responsive
        ws.send_text(json.dumps({"type": "reset"}))
        reset_ack = json.loads(ws.receive_text())
        assert reset_ack["type"] == "session_reset"


# =====================================================================
# TEST 7 — VALID FLOAT32 PCM
# =====================================================================
def test_07_valid_float32_pcm():
    """Small valid Float32 PCM signal is accepted with truthful sample count, RMS, peak, and sample rate."""
    with client.websocket_connect(f"/ws/analyze?token={AUTH_TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        # Generate 2048 samples (128ms) of 440 Hz sinusoidal Float32 PCM
        t = np.linspace(0, 0.128, 2048, endpoint=False, dtype=np.float32)
        pcm = (0.25 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
        ws.send_bytes(pcm.tobytes())

        metrics = json.loads(ws.receive_text())
        assert metrics["type"] == "audio_metrics"
        assert metrics["sample_rate"] == 16000
        assert metrics["samples"] == 2048
        assert metrics["duration_ms"] == 128.0
        assert metrics["rms"] > 0.05
        assert metrics["peak"] > 0.15


# =====================================================================
# TEST 8 — SILENCE
# =====================================================================
def test_08_silence():
    """Send zero/silent PCM. VAD reports SILENCE and does not report false genuine inference."""
    with client.websocket_connect(f"/ws/analyze?token={AUTH_TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        # Stream small silent chunk
        silent_chunk = np.zeros(1600, dtype=np.float32)
        ws.send_bytes(silent_chunk.tobytes())

        metrics = json.loads(ws.receive_text())
        assert metrics["type"] == "audio_metrics"
        assert metrics["rms"] == 0.0
        assert metrics["speech_state"] == "SILENCE"

        # Stream full 64,600 samples of pure silence
        full_silence = np.zeros(64600, dtype=np.float32)
        ws.send_bytes(full_silence.tobytes())

        # Backend must either suppress analysis or return suppressed risk with vad_speech_ratio == 0
        msg = json.loads(ws.receive_text())
        if msg.get("type") == "analysis":
            assert msg["metrics"]["vad_speech_ratio"] == 0.0
            assert msg["metrics"]["buffer_energy_rms"] == 0.0


# =====================================================================
# TEST 9 — SPEECH-LIKE AUDIO
# =====================================================================
def test_09_speech_like_audio():
    """Controlled multi-formant test signal transitions VAD to SPEECH."""
    with client.websocket_connect(f"/ws/analyze?token={AUTH_TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        # Synthesize multi-harmonic speech-like signal (300Hz fundamental + formants at 800Hz, 2400Hz)
        t = np.linspace(0, 0.2, 3200, endpoint=False, dtype=np.float32)
        speech_synth = (
            0.20 * np.sin(2 * np.pi * 300.0 * t)
            + 0.15 * np.sin(2 * np.pi * 800.0 * t)
            + 0.10 * np.sin(2 * np.pi * 2400.0 * t)
        ).astype(np.float32)
        ws.send_bytes(speech_synth.tobytes())

        metrics = json.loads(ws.receive_text())
        assert metrics["type"] == "audio_metrics"
        assert metrics["rms"] > 0.05
        assert metrics["speech_state"] == "SPEECH"


# =====================================================================
# TEST 10 — INFERENCE
# =====================================================================
def test_10_inference():
    """Verify that a valid inference window reaches the anti-spoof model."""
    with client.websocket_connect(f"/ws/analyze?token={AUTH_TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        # Prime with 64,600 samples (4.0375s)
        t = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
        audio = (0.3 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
        ws.send_bytes(audio.tobytes())

        analysis = json.loads(ws.receive_text())
        assert analysis["type"] == "analysis"
        assert analysis["status"] == "success"
        assert "anti_spoof" in analysis
        assert "score" in analysis["anti_spoof"]
        assert 0.0 <= analysis["anti_spoof"]["score"] <= 1.0
        assert analysis["pipeline_status"] == "ANALYZING"


# =====================================================================
# TEST 11 — ECAPA
# =====================================================================
def test_11_ecapa():
    """If no voiceprint exists: NO_VOICEPRINT, not MISMATCH. If enrolled: speaker verification called."""
    # 1. Unenrolled speaker
    with client.websocket_connect(f"/ws/analyze?token={AUTH_TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "start", "speaker_id": None, "format": "float32"}))
        _ = json.loads(ws.receive_text())

        t = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
        audio = (0.3 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
        ws.send_bytes(audio.tobytes())

        analysis = json.loads(ws.receive_text())
        assert analysis["type"] == "analysis"
        assert analysis["metrics"]["speaker_status"] == "NO_VOICEPRINT"
        assert analysis["metrics"]["speaker_similarity"] is None

    # 2. Enrolled speaker
    enroll_audio = (0.3 * np.sin(2 * np.pi * 300.0 * t)).astype(np.float32)
    ecapa_service.enroll_speaker("test_exec_999", enroll_audio, 16000)

    with client.websocket_connect(f"/ws/analyze?token={AUTH_TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "start", "speaker_id": "test_exec_999", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        ws.send_bytes(audio.tobytes())
        analysis = json.loads(ws.receive_text())
        assert analysis["type"] == "analysis"
        assert analysis["metrics"]["speaker_status"] in ("VERIFIED", "MISMATCH", "EVALUATING")
        assert analysis["metrics"]["speaker_similarity"] is not None


# =====================================================================
# TEST 12 — RISK ENGINE
# =====================================================================
def test_12_risk_engine():
    """Verify real signals reach the risk engine without hardcoded 0 or 100."""
    with client.websocket_connect(f"/ws/analyze?token={AUTH_TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        t = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
        audio = (0.3 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
        ws.send_bytes(audio.tobytes())

        analysis = json.loads(ws.receive_text())
        assert analysis["type"] == "analysis"
        risk_score = analysis["risk_score"]
        assert isinstance(risk_score, (int, float))
        assert 0.0 <= risk_score <= 100.0
        assert analysis["classification"] in ("LOW_RISK", "MEDIUM_RISK", "HIGH_RISK", "INSUFFICIENT_DATA")

        # Drain any residual queued messages
        ws.send_text(json.dumps({"type": "stop"}))
        _ = json.loads(ws.receive_text())

    # Test failure mode: exception must NOT yield fake score = 0
    with client.websocket_connect(f"/ws/analyze?token={AUTH_TOKEN}") as ws_err:
        ws_err.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws_err.receive_text())

        with patch("app.main.aasist_service.predict", side_effect=RuntimeError("Simulated inference failure")):
            ws_err.send_bytes(audio.tobytes())
            err_analysis = None
            for _ in range(5):
                msg = json.loads(ws_err.receive_text())
                if msg.get("type") == "analysis":
                    err_analysis = msg
                    break
            assert err_analysis is not None
            assert err_analysis["type"] == "analysis"
            assert err_analysis["status"] == "error"
            assert err_analysis["pipeline_status"] == "ANALYSIS_ERROR"
            assert "risk_score" not in err_analysis


# =====================================================================
# TEST 13 — STOP
# =====================================================================
def test_13_stop():
    """Send {"type": "stop"} returns {"type": "session_stopped"} without crash."""
    with client.websocket_connect(f"/ws/analyze?token={AUTH_TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        ws.send_text(json.dumps({"type": "stop"}))
        stopped = json.loads(ws.receive_text())
        assert stopped["type"] == "session_stopped"
        assert stopped["pipeline_status"] == "READY"


# =====================================================================
# TEST 14 — POST-STOP AUDIO
# =====================================================================
def test_14_post_stop_audio():
    """Audio sent after stop must be rejected with SESSION_NOT_ACTIVE."""
    with client.websocket_connect(f"/ws/analyze?token={AUTH_TOKEN}") as ws:
        # Start and stop
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())
        ws.send_text(json.dumps({"type": "stop"}))
        _ = json.loads(ws.receive_text())

        # Send audio after stop
        post_audio = (0.2 * np.ones(1600, dtype=np.float32)).tobytes()
        ws.send_bytes(post_audio)

        err_msg = json.loads(ws.receive_text())
        assert err_msg["type"] == "session_error"
        assert err_msg["code"] in ("SESSION_NOT_ACTIVE", "INACTIVE_SESSION")
        assert "Start an analysis session before sending audio" in err_msg["message"]


# =====================================================================
# TEST 15 — DISCONNECT
# =====================================================================
def test_15_disconnect():
    """Disconnect client. Buffers and session resources cleaned without exceptions."""
    with client.websocket_connect(f"/ws/analyze?token={AUTH_TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        chunk = (0.2 * np.ones(1600, dtype=np.float32)).tobytes()
        ws.send_bytes(chunk)
        _ = json.loads(ws.receive_text())

        # Close client websocket connection cleanly
        ws.close()

    # Verify server is completely healthy after client disconnect
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] in ("ok", "ONLINE", "degraded")
