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
