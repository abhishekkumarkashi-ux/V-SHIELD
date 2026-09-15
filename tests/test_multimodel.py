import pytest
import numpy as np
import torch
import os
from ml.pipeline.multimodel_engine import MultiModelEngine
from ml.pipeline.preprocessing import sanitize_and_prepare_audio

@pytest.fixture
def mock_engine():
    engine = MultiModelEngine()
    # Disable WavLM in tests to save memory
    engine.config["models"]["wavlm"]["enabled"] = False
    
    # We won't load real models to avoid memory issues in CI
    engine.fusion_status = "UNTRAINED_FOR_VSHIELD"
    engine.is_loaded = True
    return engine

def test_audio_preprocessing():
    # Test valid float32 numpy array
    dummy_audio = np.random.randn(16000).astype(np.float32)
    tensor = sanitize_and_prepare_audio(dummy_audio, max_length=64000)
    
    assert isinstance(tensor, torch.Tensor)
    assert tensor.shape == (1, 1, 64000) # batch, channel, length
    assert torch.max(torch.abs(tensor)) <= 1.0 # Normalized
    
    # Test stereo to mono
    stereo_audio = np.random.randn(2, 16000).astype(np.float32)
    mono_tensor = sanitize_and_prepare_audio(stereo_audio, max_length=64000)
    assert mono_tensor.shape == (1, 1, 64000)

def test_engine_initialization(mock_engine):
    assert mock_engine.is_loaded == True
    status = mock_engine.get_status()
    assert status["aasist"] == "NOT_CONFIGURED"
    assert status["wavlm"] == "NOT_CONFIGURED"

def test_engine_analyze_fallback(mock_engine):
    # Since models are NOT_CONFIGURED, it should run without crashing but return errors
    dummy_audio = np.random.randn(64000).astype(np.float32)
    result = mock_engine.analyze(dummy_audio)
    
    assert "model_status" in result
    assert "fusion" in result
    assert "risk" in result
    assert "latency" in result
    
    # Test fallback spoof probability calculation
    assert "impersonation_risk_score" in result["risk"]
