"""
Unit & integration tests for V-SHIELD Real-Time Inference Pipeline (Phase 7).
Verifies:
1. Complete processing chain: PCM -> VAD -> Buffer -> Inference Window -> Anti-Spoof -> Risk Score.
2. Explicit pipeline states: WAITING_FOR_AUDIO, LISTENING, ANALYZING, ANALYSIS_ERROR, READY.
3. Structured success payload:
   {
     "type": "analysis",
     "status": "success",
     "anti_spoof": {"score": ...},
     "risk": {"score": ...}
   }
4. Structured error payload on failure (never defaulting to score = 0):
   {
     "type": "analysis",
     "status": "error",
     "pipeline_status": "ANALYSIS_ERROR",
     "error": "..."
   }
5. Handling of unenrolled speakers (speaker_similarity is None, not 0.0).
6. Ambient silence VAD suppression in realtime stream.
"""

import json
from unittest.mock import patch

import numpy as np
from app.core.auth import get_default_operator_token
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
TOKEN = get_default_operator_token()


def test_realtime_pipeline_lifecycle_and_states():
    """Verify state transitions: READY -> WAITING_FOR_AUDIO -> LISTENING -> ANALYZING -> READY."""
    with client.websocket_connect(f"/ws/live-call?token={TOKEN}") as ws:
        # Query initial state
        ws.send_text(json.dumps({"type": "get_status"}))
        st = json.loads(ws.receive_text())
        assert st["type"] == "pipeline_status"
        assert st["status"] == "READY"

        # Start session
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        started = json.loads(ws.receive_text())
        assert started["type"] == "session_started"
        assert started["pipeline_status"] == "WAITING_FOR_AUDIO"

        # Send small audio chunk (< 64,600 samples) -> transitions to LISTENING
        t_short = np.linspace(0, 0.1, 1600, endpoint=False, dtype=np.float32)
        short_pcm = (0.2 * np.sin(2 * np.pi * 440.0 * t_short)).astype(np.float32)
        ws.send_bytes(short_pcm.tobytes())

        # Check audio_metrics packet has LISTENING status
        metrics_msg = json.loads(ws.receive_text())
        assert metrics_msg["type"] == "audio_metrics"
        assert metrics_msg["pipeline_status"] == "LISTENING"

        # Send full 64,600 samples to trigger inference window -> ANALYZING
        t_full = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
        full_pcm = (0.3 * np.sin(2 * np.pi * 440.0 * t_full)).astype(np.float32)
        ws.send_bytes(full_pcm.tobytes())

        analysis_msg = json.loads(ws.receive_text())
        assert analysis_msg["type"] == "analysis"
        assert analysis_msg["status"] == "success"
        assert analysis_msg["pipeline_status"] == "ANALYZING"
        assert "anti_spoof" in analysis_msg
        assert "score" in analysis_msg["anti_spoof"]
        assert 0.0 <= analysis_msg["anti_spoof"]["score"] <= 1.0
        assert "risk" in analysis_msg
        assert "score" in analysis_msg["risk"]
        assert 0.0 <= analysis_msg["risk"]["score"] <= 100.0

        # Stop session -> READY
        ws.send_text(json.dumps({"type": "stop"}))
        stopped = None
        while True:
            msg = json.loads(ws.receive_text())
            if msg.get("type") == "session_stopped":
                stopped = msg
                break
            assert msg.get("type") in ("analysis", "audio_metrics")

        assert stopped is not None
        assert stopped["type"] == "session_stopped"
        assert stopped["pipeline_status"] == "READY"


def test_realtime_pipeline_exception_handling_no_zero_default():
    """
    CRITICAL Phase 7 Requirement:
    Never convert an inference exception into score = 0.
    Must emit:
    {
      "type": "analysis",
      "status": "error",
      "pipeline_status": "ANALYSIS_ERROR",
      "error": "..."
    }
    """
    with client.websocket_connect(f"/ws/live-call?token={TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        # Mock aasist_service.predict to simulate runtime failure
        with patch("app.main.aasist_service.predict", side_effect=RuntimeError("CUDA execution error simulated")):
            t_full = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
            full_pcm = (0.3 * np.sin(2 * np.pi * 440.0 * t_full)).astype(np.float32)
            ws.send_bytes(full_pcm.tobytes())

            err_msg = json.loads(ws.receive_text())
            assert err_msg["type"] == "analysis"
            assert err_msg["status"] == "error"
            assert err_msg["pipeline_status"] == "ANALYSIS_ERROR"
            assert "CUDA execution error simulated" in err_msg["error"]
            # Ensure no fake score = 0 or risk score was sent
            assert "risk_score" not in err_msg
            assert "anti_spoof" not in err_msg


def test_realtime_pipeline_unenrolled_speaker_null_similarity():
    """Verify that when no speaker_id is provided, speaker_similarity is None (not 0.0)."""
    with client.websocket_connect(f"/ws/live-call?token={TOKEN}") as ws:
        # Start without speaker_id
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        t_full = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
        full_pcm = (0.3 * np.sin(2 * np.pi * 440.0 * t_full)).astype(np.float32)
        ws.send_bytes(full_pcm.tobytes())

        analysis_msg = json.loads(ws.receive_text())
        assert analysis_msg["type"] == "analysis"
        assert analysis_msg["status"] == "success"
        assert analysis_msg["metrics"]["speaker_similarity"] is None


def test_realtime_pipeline_silence_vad_suppression():
    """Verify that a window of pure silence suppresses high risk scores via VAD guard."""
    with client.websocket_connect(f"/ws/live-call?token={TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        # 64,600 samples of pure silence
        silence = np.zeros(64600, dtype=np.float32)
        ws.send_bytes(silence.tobytes())

        analysis_msg = json.loads(ws.receive_text())
        assert analysis_msg["type"] == "analysis"
        assert analysis_msg["status"] == "success"
        assert analysis_msg["metrics"]["vad_speech_ratio"] == 0.0
        # In silence, risk should be capped at 25.0
        assert analysis_msg["risk_score"] <= 25.0
