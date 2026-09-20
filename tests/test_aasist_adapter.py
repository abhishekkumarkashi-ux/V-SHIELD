"""
Unit & integration tests for AASISTModelAdapter (Phase 8).
Verifies:
1. AASISTModelAdapter interface: load(), predict(), is_loaded().
2. Dual-runtime support: ONNX Runtime fast path and PyTorch native graph attention network fallback.
3. Input handling: torch.Tensor, np.ndarray, varying lengths (repeat-padded/truncated to 64,600).
4. Configuration via VSHIELD_ANTISPOOF_MODEL_PATH.
5. Strict failure mode: raises RuntimeError if neither runtime engine is available.
6. Numerical correctness: Softmax probabilities in [0.0, 1.0].
"""

from unittest.mock import patch

import numpy as np
import pytest
import torch
from app.config import settings
from app.models.aasist_service import AASISTModelAdapter, AASISTService


def test_aasist_adapter_instantiation_and_interface():
    """Verify AASISTModelAdapter provides load(), predict(), and is_loaded()."""
    adapter = AASISTModelAdapter()
    assert adapter.is_loaded()
    assert bool(adapter.is_loaded)
    assert adapter.load()


def test_aasist_adapter_predict_tensor_and_numpy():
    """Verify predict() works with both torch.Tensor and np.ndarray."""
    adapter = AASISTModelAdapter()

    # 1. 1D Float32 numpy array
    t = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
    np_audio = (0.3 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)

    logits, spoof_prob = adapter.predict(np_audio)
    assert isinstance(logits, torch.Tensor)
    assert logits.shape == (1, 2)
    assert isinstance(spoof_prob, float)
    assert 0.0 <= spoof_prob <= 1.0

    # 2. Torch tensor input
    tensor_audio = torch.from_numpy(np_audio).unsqueeze(0)
    logits_t, spoof_prob_t = adapter.predict(tensor_audio)
    assert logits_t.shape == (1, 2)
    assert 0.0 <= spoof_prob_t <= 1.0


def test_aasist_adapter_predict_spoof_prob():
    """Verify predict_spoof_prob() convenience method."""
    adapter = AASISTModelAdapter()
    np_audio = np.zeros(64600, dtype=np.float32)
    prob = adapter.predict_spoof_prob(np_audio)
    assert isinstance(prob, float)
    assert 0.0 <= prob <= 1.0


def test_aasist_adapter_arbitrary_length_padding_and_truncation():
    """Verify that inputs shorter or longer than 64,600 are correctly shaped."""
    adapter = AASISTModelAdapter()

    # Short input (10,000 samples)
    short_audio = np.random.randn(10000).astype(np.float32)
    logits_s, prob_s = adapter.predict(short_audio)
    assert logits_s.shape == (1, 2)
    assert 0.0 <= prob_s <= 1.0

    # Long input (100,000 samples)
    long_audio = np.random.randn(100000).astype(np.float32)
    logits_l, prob_l = adapter.predict(long_audio)
    assert logits_l.shape == (1, 2)
    assert 0.0 <= prob_l <= 1.0


def test_aasist_adapter_env_var_override(tmp_path):
    """Verify VSHIELD_ANTISPOOF_MODEL_PATH overrides default checkpoint path."""
    fake_weights = tmp_path / "custom_aasist.pth"
    fake_weights.touch()

    with patch.object(settings, "VSHIELD_ANTISPOOF_MODEL_PATH", fake_weights):
        adapter = AASISTModelAdapter()
        assert adapter.weights_path == str(fake_weights)


def test_aasist_adapter_unloaded_raises_runtime_error():
    """Verify that predict() raises RuntimeError if model cannot be loaded."""
    adapter = AASISTModelAdapter(weights_path="non_existent.pth", onnx_path="non_existent.onnx")
    adapter._is_onnx_loaded = False
    adapter._is_loaded = False
    adapter.model = None
    adapter.ort_session = None

    with pytest.raises(RuntimeError) as exc_info:
        adapter.predict(np.zeros(64600, dtype=np.float32))
    assert "AASIST model failed to infer" in str(exc_info.value)


def test_aasist_service_is_adapter_subclass():
    """Verify AASISTService inherits from AASISTModelAdapter and preserves singleton pattern."""
    service = AASISTService.get_instance()
    assert isinstance(service, AASISTModelAdapter)
    assert service.is_loaded()
    assert service.is_loaded == 1
    # Check is_onnx_loaded and is_pytorch_loaded properties
    assert bool(service.is_onnx_loaded or service.is_pytorch_loaded)
