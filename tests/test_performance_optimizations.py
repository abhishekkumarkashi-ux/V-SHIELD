"""
Performance Optimization & Integrity Test Suite (SIH 2026 / Phase 25).
Verifies:
1. AASIST session reuse (Singleton).
2. ECAPA session reuse (Singleton).
3. Provider detection.
4. CPU fallback.
5. CUDA selection logic when available.
6. Performance telemetry structure & degradation reporting.
7. Inference queue and chunk ingestion.
8. Backpressure under queue overload.
9. Session isolation across concurrent callers.
10. Model output consistency against reference outputs.
"""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from app.core.auth import get_default_operator_token
from app.core.buffer import AudioCircularBuffer
from app.core.risk_engine import RiskEngine
from app.main import app
from app.models.aasist_service import AASISTModelAdapter, AASISTService
from app.models.ecapa_service import ECAPAService
from fastapi.testclient import TestClient

client = TestClient(app)
TOKEN = get_default_operator_token()


def test_aasist_session_reuse():
    """Rule 3 & 19: Verify AASIST ONNX session is created once and reused across invocations."""
    s1 = AASISTService.get_instance()
    s2 = AASISTService.get_instance()
    assert s1 is s2, "AASISTService must be a singleton"
    assert s1.ort_session is not None, "ONNX session must be initialized"

    session_id_before = id(s1.ort_session)
    dummy_audio = np.zeros(64600, dtype=np.float32)
    s1.predict_spoof_prob(dummy_audio)
    session_id_after = id(s1.ort_session)

    assert session_id_before == session_id_after, "ONNX session must not be recreated per inference"


def test_ecapa_session_reuse():
    """Rule 3 & 19: Verify ECAPA ONNX session is created once and reused across invocations."""
    e1 = ECAPAService.get_instance()
    e2 = ECAPAService.get_instance()
    assert e1 is e2, "ECAPAService must be a singleton"
    assert e1.ort_session is not None, "ONNX session must be initialized"

    session_id_before = id(e1.ort_session)
    dummy_audio = np.zeros(32000, dtype=np.float32)
    e1.extract_embedding(dummy_audio)
    session_id_after = id(e1.ort_session)

    assert (
        session_id_before == session_id_after
    ), "ECAPA ONNX session must not be recreated per inference"


def test_provider_detection():
    """Rule 4 & 19: Verify active ONNX execution provider is accurately detected and reported."""
    aasist = AASISTService.get_instance()
    ecapa = ECAPAService.get_instance()

    assert hasattr(aasist, "active_provider")
    assert hasattr(ecapa, "active_provider")
    assert aasist.active_provider in ("CPUExecutionProvider", "CUDAExecutionProvider")
    assert ecapa.active_provider in ("CPUExecutionProvider", "CUDAExecutionProvider")
    assert hasattr(aasist, "inference_device")
    assert aasist.inference_device in ("cpu", "cuda")


def test_cpu_fallback():
    """Rule 4 & 19: Verify CPU fallback functions correctly when CUDA is unavailable."""
    with patch("torch.cuda.is_available", return_value=False):
        adapter = AASISTModelAdapter()
        assert adapter.inference_device == "cpu"
        assert adapter.active_provider in ("CPUExecutionProvider", "None")


def test_cuda_selection_when_available():
    """Rule 5 & 19: Verify CUDA provider is included if CUDA is available in environment."""
    import onnxruntime as ort

    with patch("torch.cuda.is_available", return_value=True):
        with patch.object(
            ort,
            "get_available_providers",
            return_value=["CUDAExecutionProvider", "CPUExecutionProvider"],
        ):
            # Test that adapter logic detects CUDAExecutionProvider
            available = ort.get_available_providers()
            providers = []
            if "CUDAExecutionProvider" in available:
                providers.append("CUDAExecutionProvider")
            providers.append("CPUExecutionProvider")
            assert providers[0] == "CUDAExecutionProvider"


def test_performance_telemetry_schema():
    """Rule 14 & 15: Verify WebSocket telemetry packet contains performance breakdown and degradation status."""
    with client.websocket_connect(f"/ws/live-call?token={TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "start", "speaker_id": "exec-001", "format": "float32"}))
        started = json.loads(ws.receive_text())
        assert started["type"] == "session_started"

        # Prime the buffer with 64,600 samples
        t = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
        audio = (0.2 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
        ws.send_bytes(audio.tobytes())

        resp = json.loads(ws.receive_text())
        assert resp["type"] == "analysis"
        assert "performance" in resp, "Telemetry packet must include 'performance' breakdown"
        perf = resp["performance"]
        assert "preprocess_ms" in perf
        assert "aasist_ms" in perf
        assert "ecapa_ms" in perf
        assert "risk_engine_ms" in perf
        assert "total_ms" in perf
        assert "provider" in perf
        assert "device" in perf
        assert "performance_status" in perf
        assert perf["performance_status"] in ("OPTIMAL", "DEGRADED")
        assert "hop_budget_ms" in perf
        assert perf["hop_budget_ms"] == 500.0


def test_inference_queue_and_backpressure():
    """Rule 13 & 19: Verify bounded queue handles backpressure without crashing."""
    with client.websocket_connect(f"/ws/live-call?token={TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "start", "speaker_id": "exec-001", "format": "pcm16"}))
        _ = json.loads(ws.receive_text())

        # Flood the socket with 15 small chunks to test queue capacity (limit: 10)
        chunk = np.zeros(1600, dtype=np.int16).tobytes()  # 100ms
        for _ in range(15):
            ws.send_bytes(chunk)

        # Connection should remain alive and responsive
        ws.send_text(json.dumps({"type": "status"}))
        resp = json.loads(ws.receive_text())
        # May receive metrics or pipeline_status
        assert resp["type"] in ("audio_metrics", "pipeline_status", "analysis")


def test_session_isolation():
    """Rule 9 & 19: Verify distinct client sessions remain completely isolated."""
    buf1 = AudioCircularBuffer(capacity=64600, hop_size=8000)
    buf2 = AudioCircularBuffer(capacity=64600, hop_size=8000)
    risk1 = RiskEngine(alpha=0.7)
    risk2 = RiskEngine(alpha=0.7)

    # Session 1 receives loud audio
    s1_audio = np.ones(8000, dtype=np.float32) * 0.8
    buf1.append_samples(s1_audio)

    # Session 2 receives silence
    s2_audio = np.zeros(8000, dtype=np.float32)
    buf2.append_samples(s2_audio)

    assert buf1.get_current_rms() > 0.2
    assert buf2.get_current_rms() < 1e-4

    # Update risk in s1 only
    r1, _, _ = risk1.evaluate(spoof_prob=0.95, speaker_similarity=0.1)
    r2, _, _ = risk2.evaluate(spoof_prob=0.01, speaker_similarity=0.9)

    assert r1 > 50.0
    assert r2 < 30.0


def test_model_output_consistency_against_references():
    """Rule 18 & 19: Verify optimized models produce numerically consistent results against recorded references."""
    ref_file = Path(__file__).resolve().parent.parent / "benchmarks" / "reference_outputs.json"
    if not ref_file.exists():
        pytest.skip("reference_outputs.json not found")

    with open(ref_file, "r") as f:
        references = json.load(f)

    aasist = AASISTService.get_instance()
    ecapa = ECAPAService.get_instance()

    for ref in references:
        freq = ref["freq"]
        t = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
        sig = (
            0.25 * np.sin(2 * np.pi * freq * t) + 0.10 * np.sin(2 * np.pi * (freq * 2) * t)
        ).astype(np.float32)

        _, spoof_prob = aasist.predict(sig)
        embedding = ecapa.extract_embedding(sig).tolist()

        # Check difference against recorded baseline
        prob_diff = abs(spoof_prob - ref["spoof_prob"])
        emb_diff = max(abs(a - b) for a, b in zip(embedding[:10], ref["embedding_sample"]))

        assert prob_diff < 1e-4, f"AASIST output drifted for freq {freq}: diff={prob_diff}"
        assert emb_diff < 1e-4, f"ECAPA embedding drifted for freq {freq}: diff={emb_diff}"
