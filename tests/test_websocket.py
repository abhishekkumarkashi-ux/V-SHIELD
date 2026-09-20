"""
Integration tests for V-SHIELD WebSocket protocol on /ws/live-call and /ws/analyze (SIH 2026).
Verifies:
1. Start message initiates session (session_started).
2. Stop message halts session without closing socket (session_stopped).
3. Reset message clears buffers and returns session_reset.
4. Malformed JSON returns protocol_error without dropping connection.
5. Empty binary returns audio_error without dropping connection.
6. Speaker switching via switch_speaker control frame.
7. Both /ws/live-call and /ws/analyze routes work identically.
"""

import json

import pytest
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.mark.parametrize("endpoint", ["/ws/live-call", "/ws/analyze"])
def test_websocket_start_and_stop_session(endpoint):
    """Verify start/stop session lifecycle preserves socket connection on both endpoints."""
    with client.websocket_connect(endpoint) as ws:
        # 1. Send start
        ws.send_text(json.dumps({"type": "start", "speaker_id": "exec-001"}))
        started = json.loads(ws.receive_text())
        assert started["type"] == "session_started"
        assert started["speaker_id"] == "exec-001"
        assert "session_id" in started

        # 2. Send stop
        ws.send_text(json.dumps({"type": "stop"}))
        stopped = json.loads(ws.receive_text())
        assert stopped["type"] == "session_stopped"

        # 3. Socket must still be open: send reset
        ws.send_text(json.dumps({"type": "reset"}))
        reset_resp = json.loads(ws.receive_text())
        assert reset_resp["type"] == "session_reset"


def test_websocket_malformed_json_handling():
    """Verify invalid JSON returns protocol_error and does not crash the gateway."""
    with client.websocket_connect("/ws/live-call") as ws:
        # Send invalid JSON
        ws.send_text("{bad-json")
        err_msg = json.loads(ws.receive_text())
        assert err_msg["type"] == "protocol_error"
        assert "Malformed JSON" in err_msg["error"]

        # Socket still responsive
        ws.send_text(json.dumps({"type": "reset"}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "session_reset"


def test_websocket_empty_binary_handling():
    """Verify empty binary packet returns audio_error safely."""
    with client.websocket_connect("/ws/live-call") as ws:
        # Send 0-length bytes
        ws.send_bytes(b"")
        err_msg = json.loads(ws.receive_text())
        assert err_msg["type"] == "audio_error"
        assert "Empty audio packet" in err_msg["error"]


def test_websocket_switch_speaker():
    """Verify speaker_id switching on-the-fly."""
    with client.websocket_connect("/ws/live-call") as ws:
        ws.send_text(json.dumps({"type": "switch_speaker", "speaker_id": "exec-002"}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "speaker_switched"
        assert resp["speaker_id"] == "exec-002"


def test_websocket_float32_pcm_streaming():
    """Verify raw 16kHz Float32 PCM streaming over WebSocket produces telemetry packets."""
    import numpy as np

    with client.websocket_connect("/ws/live-call") as ws:
        # Start session with float32 format
        ws.send_text(json.dumps({"type": "start", "speaker_id": "exec-001", "format": "float32"}))
        started = json.loads(ws.receive_text())
        assert started["type"] == "session_started"
        assert started["format"] == "float32"

        # Send 64,600 samples of 16kHz Float32 audio (4.0375s) to prime buffer
        t = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
        f32_audio = (0.4 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
        ws.send_bytes(f32_audio.tobytes())

        telemetry = json.loads(ws.receive_text())
        assert telemetry["type"] == "analysis"
        assert "risk_score" in telemetry
        assert "metrics" in telemetry
        assert telemetry["metrics"]["buffer_energy_rms"] > 0.0


def test_websocket_audio_packet_too_small():
    """Verify audio packets smaller than 4 bytes return audio_error."""
    with client.websocket_connect("/ws/live-call") as ws:
        ws.send_bytes(b"\x00\x01")
        err_msg = json.loads(ws.receive_text())
        assert err_msg["type"] == "audio_error"
        assert "too small" in err_msg["error"]


def test_websocket_misaligned_float32_audio():
    """Verify misaligned Float32 audio chunks return audio_error."""
    with client.websocket_connect("/ws/live-call") as ws:
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        ws.send_bytes(b"\x00" * 7)  # 7 is not divisible by 4
        err_msg = json.loads(ws.receive_text())
        assert err_msg["type"] == "audio_error"
        assert "not divisible by 4" in err_msg["error"]


def test_websocket_non_finite_float32_audio():
    """Verify Float32 audio with NaNs or Infs is rejected safely."""
    import numpy as np

    with client.websocket_connect("/ws/live-call") as ws:
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        dirty_audio = np.array([0.1, np.nan, 0.5, np.inf], dtype=np.float32)
        ws.send_bytes(dirty_audio.tobytes())

        err_msg = json.loads(ws.receive_text())
        assert err_msg["type"] == "audio_error"
        assert "Non-finite" in err_msg["error"]


def test_websocket_out_of_bounds_amplitude_audio():
    """Verify extreme amplitude audio (> 10.0 peak) is rejected."""
    import numpy as np

    with client.websocket_connect("/ws/live-call") as ws:
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        extreme_audio = (np.ones(100, dtype=np.float32) * 50.0).tobytes()
        ws.send_bytes(extreme_audio)

        err_msg = json.loads(ws.receive_text())
        assert err_msg["type"] == "audio_error"
        assert "out of bounds" in err_msg["error"]


def test_websocket_audio_metrics_packet_reporting():
    """Verify unprimed audio chunks emit audio_metrics telemetry for frontend instrumentation."""
    import numpy as np

    with client.websocket_connect("/ws/live-call") as ws:
        ws.send_text(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(ws.receive_text())

        # Send 2048 samples (128ms) of 440 Hz audio
        t = np.linspace(0, 0.128, 2048, endpoint=False, dtype=np.float32)
        chunk = (0.3 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
        ws.send_bytes(chunk.tobytes())

        metrics_msg = json.loads(ws.receive_text())
        assert metrics_msg["type"] == "audio_metrics"
        assert metrics_msg["sample_rate"] == 16000
        assert metrics_msg["samples"] == 2048
        assert metrics_msg["duration_ms"] == 128.0
        assert metrics_msg["rms"] > 0.1
        assert metrics_msg["peak"] > 0.2
