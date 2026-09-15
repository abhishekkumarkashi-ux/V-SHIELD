import os
import io
import sys
import numpy as np
import soundfile as sf
import pytest
from fastapi.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
repo_dir = os.path.abspath(os.path.join(backend_dir, '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if repo_dir not in sys.path:
    sys.path.insert(0, repo_dir)

from app.main import app
from app.ml.model import model_instance
from app.ml.speaker_verification import speaker_verification_instance

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_models_and_user():
    base_dir = repo_dir
    model_path = os.path.join(base_dir, 'models', 'vshield_antispoof_v1', 'best_model.pt')
    if os.path.exists(model_path) and not model_instance.is_loaded:
        model_instance.load_model(model_path)

    if not speaker_verification_instance.is_loaded:
        speaker_verification_instance.load_model()

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


def generate_wav_bytes(duration_sec=3.0, sample_rate=16000):
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format='WAV')
    buf.seek(0)
    return buf.read()


def test_root_endpoint():
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert data["service"] == "V-SHIELD Backend"


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["model_loaded"] is True
    assert data["model_status"] == "UNTRAINED"
    assert data["production_ready"] is False
    assert "Anti-spoofing model is not validated" in data["model_disclaimer"]


def test_auth_missing_fields():
    res = client.post("/api/v1/auth/login", json={"email": "dev@vshield.app"})
    assert res.status_code == 422


def test_auth_invalid_credentials():
    res = client.post("/api/v1/auth/login", json={"email": "dev@vshield.app", "password": "wrongpassword"})
    assert res.status_code == 401


def test_auth_unauthenticated_me():
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


def test_auth_lifecycle_and_protected_routes():
    # 1. Login with valid credentials
    login_res = client.post("/api/v1/auth/login", json={"email": "dev@vshield.app", "password": "admin123"})
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["status"] == "success"
    assert "access_token" in login_data
    token = login_data["access_token"]
    assert "vshield_session" in login_res.cookies

    # 2. Get /me authenticated
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "dev@vshield.app"

    # 3. GET /status authenticated
    status_res = client.get("/api/v1/status", headers={"Authorization": f"Bearer {token}"})
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["system"] == "online"
    assert status_data["ml_model"]["model_status"] == "UNTRAINED"
    assert status_data["ml_model"]["production_ready"] is False

    # 4. GET /history authenticated
    hist_res = client.get("/api/v1/history", headers={"Authorization": f"Bearer {token}"})
    assert hist_res.status_code == 200
    assert isinstance(hist_res.json(), list)

    # 5. POST /analyze with valid wav
    wav_bytes = generate_wav_bytes(4.0)
    analyze_res = client.post(
        "/api/v1/analyze",
        files={"file": ("test_voice.wav", wav_bytes, "audio/wav")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert analyze_res.status_code == 200
    analyze_data = analyze_res.json()
    assert "spoof_probability" in analyze_data
    assert analyze_data["model_status"] == "UNTRAINED"
    assert analyze_data["production_ready"] is False

    # 6. POST /analyze with invalid extension
    bad_res = client.post(
        "/api/v1/analyze",
        files={"file": ("test_doc.pdf", b"not audio data", "application/pdf")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert bad_res.status_code == 400

    # 7. POST /enroll with valid audio
    enroll_res = client.post(
        "/api/v1/enroll",
        files={"file": ("enrollment.wav", wav_bytes, "audio/wav")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert enroll_res.status_code == 200
    assert enroll_res.json()["status"] == "success"

    # 8. POST /logout
    logout_res = client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200

    # 9. After logout without Bearer header (cookie was cleared)
    me_after = client.get("/api/v1/auth/me")
    assert me_after.status_code == 401


def test_unauthenticated_protected_endpoints():
    unauth_client = TestClient(app)
    assert unauth_client.get("/api/v1/status").status_code == 401
    assert unauth_client.get("/api/v1/history").status_code == 401
    assert unauth_client.post("/api/v1/analyze").status_code == 401
    assert unauth_client.post("/api/v1/enroll").status_code == 401
