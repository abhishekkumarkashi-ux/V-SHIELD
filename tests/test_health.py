"""
Unit & Integration tests for /health and /api/health endpoints (SIH 2026).
Verifies:
1. /health returns HTTP 200 with truthful model readiness telemetry.
2. /api/health compatibility endpoint returns identical schema.
3. Accurate reflection of device, model_loaded, and anti_spoof_model.
4. Degraded status when model availability is perturbed.
"""

from app.main import app, print_startup_banner
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_endpoint_success():
    """Verify /health returns HTTP 200 and truthful model_loaded state."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["model_loaded"] is True
    assert data["device"] in ["cuda", "cpu"]
    assert "AASIST" in data["anti_spoof_model"]
    assert data["speaker_verification_loaded"] is True
    assert isinstance(data["enrolled_speakers_count"], int)
    assert data["enrolled_speakers_count"] >= 0


def test_api_health_endpoint_alias():
    """Verify /api/health returns HTTP 200 and matches /health."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["model_loaded"] is True
    assert data["aasist_loaded"] is True
    assert data["ecapa_loaded"] is True


def test_health_reflects_unloaded_model():
    """Verify model_loaded is False and status is degraded when a model is not loaded."""
    from app.main import aasist_service

    orig_onnx = aasist_service.is_onnx_loaded
    orig_loaded = aasist_service.is_loaded
    try:
        aasist_service.is_onnx_loaded = False
        aasist_service.is_loaded = False
        aasist_service.load_error = "Simulated missing weights for test"

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()

        assert data["model_loaded"] is False
        assert data["status"] in ["degraded", "error"]
        assert data["details"] is not None
        assert "Simulated missing weights" in data["details"].get("aasist_error", "")
    finally:
        aasist_service.is_onnx_loaded = orig_onnx
        aasist_service.is_loaded = orig_loaded
        aasist_service.load_error = None


def test_startup_banner_execution(capsys):
    """Verify startup banner prints cleanly with all diagnostic telemetry."""
    print_startup_banner()
    captured = capsys.readouterr()
    assert "V-SHIELD BACKEND STARTUP" in captured.out
    assert "Python:" in captured.out
    assert "Anti-spoof model:" in captured.out
    assert "Speaker verification:" in captured.out
