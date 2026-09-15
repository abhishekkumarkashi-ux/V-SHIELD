import pytest
from fastapi.testclient import TestClient
import numpy as np
import json
import sys
import os

# Ensure backend and repo root are in path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
repo_dir = os.path.abspath(os.path.join(backend_dir, '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if repo_dir not in sys.path:
    sys.path.insert(0, repo_dir)

from app.main import app
from app.ml.model import model_instance

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def ensure_test_setup():
    """Ensure models and seed user exist for tests."""
    base_dir = repo_dir
    model_path = os.path.join(base_dir, 'models', 'vshield_antispoof_v1', 'best_model.pt')
    if os.path.exists(model_path) and not model_instance.is_loaded:
        model_instance.load_model(model_path)
    
    # Ensure seed user in DB
    from app.database.database import SessionLocal
    from app.database.models import User
    import bcrypt
    
    db = SessionLocal()
    dev_user = db.query(User).filter(User.email == "dev@vshield.app").first()
    if not dev_user:
        hashed_pw = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        new_user = User(
            email="dev@vshield.app",
            name="Developer User",
            hashed_password=hashed_pw
        )
        db.add(new_user)
        db.commit()
    db.close()


def test_websocket_unauthenticated_audio_rejection():
    """P0-02: Sending binary audio without authentication must be rejected with code 1008."""
    with client.websocket_connect("/ws/analyze") as ws:
        init_data = ws.receive_json()
        assert init_data["type"] == "status"
        assert init_data["status"] == "connected"

        # Directly send binary audio chunk without authenticating
        dummy_audio = np.zeros(16000, dtype=np.float32).tobytes()
        ws.send_bytes(dummy_audio)

        # Expect error message followed by close
        err_msg = ws.receive_json()
        assert err_msg["type"] == "error"
        assert "Authentication required" in err_msg["message"]


def test_websocket_unauthorized_origin_rejection():
    """P1-04: Connections from unauthorized origins must be rejected with code 1008."""
    headers = {"Origin": "http://malicious-site.attacker.com"}
    with client.websocket_connect("/ws/analyze", headers=headers) as ws:
        err_msg = ws.receive_json()
        assert err_msg["type"] == "error"
        assert "Unauthorized origin" in err_msg["message"]


def test_websocket_ping_pong_and_unknown_commands():
    """Test ping-pong protocol and unknown command rejection."""
    with client.websocket_connect("/ws/analyze") as ws:
        ws.receive_json()  # connected

        # Ping
        ws.send_text(json.dumps({"type": "ping"}))
        pong = ws.receive_json()
        assert pong["type"] == "pong"

        # Unknown command
        ws.send_text(json.dumps({"type": "execute_malicious_action"}))
        err = ws.receive_json()
        assert err["type"] == "error"
        assert "Unsupported protocol message" in err["message"]


def test_websocket_authenticated_full_pipeline():
    """Test full authenticated live analysis pipeline."""
    # 1. Login to retrieve real JWT
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "dev@vshield.app", "password": "admin123"}
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]

    with client.websocket_connect("/ws/analyze") as ws:
        # Connected handshake
        conn_data = ws.receive_json()
        assert conn_data["type"] == "status"
        assert conn_data["status"] == "connected"
        assert "protocol" in conn_data

        # Authenticate via start message
        ws.send_text(json.dumps({"type": "start", "token": token}))

        auth_data = ws.receive_json()
        assert auth_data["type"] == "status"
        assert auth_data["status"] == "authenticated"

        analyzing_data = ws.receive_json()
        assert analyzing_data["type"] == "status"
        assert analyzing_data["status"] == "analyzing"
        assert analyzing_data["model_status"] == "UNTRAINED"
        assert analyzing_data["production_ready"] is False

        # Send silence chunk (16,000 samples of 0.0)
        silence_chunk = np.zeros(16000, dtype=np.float32).tobytes()
        ws.send_bytes(silence_chunk)

        vad_data = ws.receive_json()
        assert vad_data["type"] == "analysis"
        assert vad_data["status"] == "silence"
        assert vad_data["vad"] == "SILENCE"

        # Send speech chunk (synthetic tone with high energy)
        t = np.linspace(0, 1.0, 16000, endpoint=False)
        tone = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32).tobytes()
        ws.send_bytes(tone)

        buf_data = ws.receive_json()
        assert buf_data["type"] == "analysis"
        assert buf_data["status"] == "buffering"
        assert buf_data["vad"] == "SPEECH"

        # Fill buffer up to 64,000 samples (send 3 more 16,000-sample chunks)
        inference_result = None
        for _ in range(5):
            ws.send_bytes(tone)
            res = ws.receive_json()
            if res.get("status") == "success":
                inference_result = res
                break

        assert inference_result is not None, "Full-window inference was not triggered"
        assert "spoof_probability" in inference_result
        assert "impersonation_risk_score" in inference_result
        assert inference_result["model_status"] == "UNTRAINED"
        assert inference_result["production_ready"] is False
        assert "Anti-spoofing model is not validated" in inference_result["model_disclaimer"]

        # Stop session
        ws.send_text(json.dumps({"type": "stop"}))
        stop_data = ws.receive_json()
        assert stop_data["type"] == "status"
        assert stop_data["status"] == "stopped"


def test_websocket_malformed_frames():
    """Test malformed frame handling (odd bytes, NaN values) with authentication."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "dev@vshield.app", "password": "admin123"}
    )
    token = login_res.json()["access_token"]

    with client.websocket_connect("/ws/analyze") as ws:
        ws.receive_json()  # connected
        ws.send_text(json.dumps({"type": "start", "token": token}))
        ws.receive_json()  # authenticated
        ws.receive_json()  # analyzing

        # 1. Invalid byte alignment (not multiple of 4)
        ws.send_bytes(b"\x00\x01\x02")
        err1 = ws.receive_json()
        assert err1["type"] == "analysis"
        assert err1["status"] == "error"
        assert "multiple of 4" in err1["error"]

        # 2. Non-finite values (NaN)
        nan_chunk = np.array([np.nan] * 100, dtype=np.float32).tobytes()
        ws.send_bytes(nan_chunk)
        err2 = ws.receive_json()
        assert err2["type"] == "analysis"
        assert err2["status"] == "error"
        assert "non-finite" in err2["error"]


def test_websocket_oversized_frame():
    """Test that frames exceeding 512 KB are closed with code 1009."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "dev@vshield.app", "password": "admin123"}
    )
    token = login_res.json()["access_token"]

    with client.websocket_connect("/ws/analyze") as ws:
        ws.receive_json()  # connected
        ws.send_text(json.dumps({"type": "start", "token": token}))
        ws.receive_json()  # authenticated
        ws.receive_json()  # analyzing

        # Frame larger than 512 KB (512 * 1024 + 4 bytes)
        oversized = np.zeros(131073, dtype=np.float32).tobytes()  # 524,292 bytes
        ws.send_bytes(oversized)

        err = ws.receive_json()
        assert err["type"] == "error"
        assert "exceeds limit" in err["message"]
