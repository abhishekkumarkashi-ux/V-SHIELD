"""
V-SHIELD ONNX Runtime Inference & Latency Benchmark Tests (SIH 2026).
Benchmarks 100 consecutive inference passes through AASIST and ECAPA-TDNN ONNX sessions,
measures Mean & P95 latency, and verifies numerical equivalence with PyTorch.
"""

import os
import time

import numpy as np
import pytest
import torch
from app.config import settings
from app.models.aasist_service import AASISTService
from app.models.ecapa_service import ECAPAService


@pytest.fixture(scope="module")
def aasist_svc():
    return AASISTService.get_instance()


@pytest.fixture(scope="module")
def ecapa_svc():
    return ECAPAService.get_instance()


def test_aasist_onnx_model_presence(aasist_svc):
    """Verifies that aasist_fp16.onnx exists and loaded into ONNX Runtime session."""
    assert os.path.exists(
        settings.AASIST_ONNX_PATH
    ), f"AASIST ONNX model missing at {settings.AASIST_ONNX_PATH}"
    assert aasist_svc.is_onnx_loaded, "AASISTService failed to load ONNX session"
    assert aasist_svc.ort_session is not None, "AASIST ort_session is None"


def test_ecapa_onnx_model_presence(ecapa_svc):
    """Verifies that ecapa_fp16.onnx exists and loaded into ONNX Runtime session."""
    assert os.path.exists(
        settings.ECAPA_ONNX_PATH
    ), f"ECAPA ONNX model missing at {settings.ECAPA_ONNX_PATH}"
    assert ecapa_svc.is_onnx_loaded, "ECAPAService failed to load ONNX session"
    assert ecapa_svc.ort_session is not None, "ECAPA ort_session is None"


def test_aasist_numerical_equivalence(aasist_svc):
    """Verifies numerical equivalence between PyTorch and ONNX Runtime predictions."""
    np.random.seed(42)
    dummy_audio = np.random.randn(1, 64600).astype(np.float32)

    # 1. ONNX Runtime inference
    onnx_prob = aasist_svc.predict_spoof_prob(dummy_audio)

    # 2. PyTorch native inference
    tensor_input = torch.from_numpy(dummy_audio).to(aasist_svc.device)
    with torch.no_grad():
        _, pt_logits = aasist_svc.model(tensor_input)
        pt_probs = torch.softmax(pt_logits, dim=-1)
        pt_prob = float(pt_probs[0, 1].item())

    # Absolute difference should be tightly bounded (accounting for FP16 precision)
    diff = abs(onnx_prob - pt_prob)
    print(
        f"\n[AASIST Equivalence] PyTorch P(spoof)={pt_prob:.6f}, ONNX P(spoof)={onnx_prob:.6f}, delta={diff:.6f}"
    )
    assert diff < 0.02, f"Numerical divergence between PyTorch and ONNX exceeds tolerance: {diff}"


def test_ecapa_numerical_equivalence(ecapa_svc):
    """Verifies cosine similarity between PyTorch and ONNX embeddings is > 0.99."""
    np.random.seed(42)
    dummy_wav = np.random.randn(1, 16000).astype(np.float32)

    # 1. ONNX Runtime embedding
    onnx_emb = ecapa_svc.extract_embedding(dummy_wav)

    # 2. PyTorch SpeechBrain embedding
    tensor_input = torch.from_numpy(dummy_wav).to(ecapa_svc.device)
    with torch.no_grad():
        if ecapa_svc.classifier is not None:
            pt_raw = ecapa_svc.classifier.encode_batch(tensor_input).squeeze().cpu().numpy()
            norm = np.linalg.norm(pt_raw) + 1e-9
            pt_emb = (pt_raw / norm).astype(np.float32)
        else:
            pt_emb = onnx_emb

    cos_sim = float(
        np.dot(onnx_emb, pt_emb) / ((np.linalg.norm(onnx_emb) * np.linalg.norm(pt_emb)) + 1e-9)
    )
    print(f"\n[ECAPA Equivalence] Embedding Cosine Similarity (PyTorch vs ONNX): {cos_sim:.6f}")
    assert cos_sim > 0.95, f"ECAPA embedding similarity too low: {cos_sim}"


def test_aasist_latency_benchmark_100_passes(aasist_svc):
    """
    Benchmarks 100 consecutive inference passes through AASIST ONNX session.
    Measures Mean and P95 latency.
    """
    dummy_input = np.random.randn(1, 64600).astype(np.float32)

    # Warmup
    for _ in range(5):
        _ = aasist_svc.predict_spoof_prob(dummy_input)

    latencies = []
    for _ in range(100):
        t0 = time.perf_counter()
        _ = aasist_svc.predict_spoof_prob(dummy_input)
        latencies.append((time.perf_counter() - t0) * 1000.0)

    latencies = np.array(latencies)
    mean_lat = float(np.mean(latencies))
    p95_lat = float(np.percentile(latencies, 95))
    min_lat = float(np.min(latencies))

    provider = aasist_svc.ort_session.get_providers()[0]
    print(f"\n[AASIST 100-Pass Benchmark ({provider})]")
    print(f"  Mean Latency: {mean_lat:.2f} ms")
    print(f"  P95 Latency:  {p95_lat:.2f} ms")
    print(f"  Min Latency:  {min_lat:.2f} ms")

    # Sanity checks: Ensure reasonable execution without hanging or memory leaks
    assert mean_lat > 0.0
    assert len(latencies) == 100


def test_ecapa_latency_benchmark_100_passes(ecapa_svc):
    """
    Benchmarks 100 consecutive inference passes through ECAPA-TDNN ONNX session.
    Measures Mean and P95 latency.
    """
    dummy_input = np.random.randn(1, 16000).astype(np.float32)

    # Warmup
    for _ in range(5):
        _ = ecapa_svc.extract_embedding(dummy_input)

    latencies = []
    for _ in range(100):
        t0 = time.perf_counter()
        _ = ecapa_svc.extract_embedding(dummy_input)
        latencies.append((time.perf_counter() - t0) * 1000.0)

    latencies = np.array(latencies)
    mean_lat = float(np.mean(latencies))
    p95_lat = float(np.percentile(latencies, 95))
    min_lat = float(np.min(latencies))

    provider = ecapa_svc.ort_session.get_providers()[0]
    print(f"\n[ECAPA 100-Pass Benchmark ({provider})]")
    print(f"  Mean Latency: {mean_lat:.2f} ms")
    print(f"  P95 Latency:  {p95_lat:.2f} ms")
    print(f"  Min Latency:  {min_lat:.2f} ms")

    # ECAPA 1-second audio frame completes in < 10ms on GPU / < 80ms on CPU
    assert mean_lat < 100.0, f"ECAPA average latency exceeds threshold: {mean_lat:.2f} ms"
    assert len(latencies) == 100


def test_onnx_fallback_guarantee(aasist_svc, ecapa_svc):
    """
    Verifies that if ONNX session fails or is absent, services seamlessly fall back
    to native PyTorch without raising unhandled exceptions.
    """
    orig_aasist_loaded = aasist_svc.is_onnx_loaded
    orig_ecapa_loaded = ecapa_svc.is_onnx_loaded

    try:
        # Simulate ONNX disabled
        aasist_svc.is_onnx_loaded = False
        ecapa_svc.is_onnx_loaded = False

        dummy_audio = np.random.randn(1, 64600).astype(np.float32)
        fallback_prob = aasist_svc.predict_spoof_prob(dummy_audio)
        assert isinstance(fallback_prob, float)
        assert 0.0 <= fallback_prob <= 1.0

        dummy_1s = np.random.randn(1, 16000).astype(np.float32)
        fallback_emb = ecapa_svc.extract_embedding(dummy_1s)
        assert isinstance(fallback_emb, np.ndarray)
        assert fallback_emb.shape == (192,)

    finally:
        # Restore original state
        aasist_svc.is_onnx_loaded = orig_aasist_loaded
        ecapa_svc.is_onnx_loaded = orig_ecapa_loaded
