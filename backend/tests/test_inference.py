import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.ml.model import model_instance

def test_inference():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    model_path = os.path.join(base_dir, 'models', 'vshield_antispoof_v1', 'best_model.pt')
    
    if not os.path.exists(model_path):
        pytest.fail(f"Model path does not exist: {model_path}. Cannot test inference without checkpoint.")
        
    model_instance.load_model(model_path)
    assert model_instance.is_loaded == True, "Model should load successfully"
    
    # Dummy valid PCM: 4 seconds of 16kHz float32
    dummy_audio = np.random.uniform(-1.0, 1.0, 64000).astype(np.float32)
    
    result = model_instance.predict_pcm(dummy_audio)
    
    assert "error" not in result, f"Inference returned error: {result.get('error')}"
    assert "spoof_probability" in result, "Result must contain spoof_probability"
    
    prob = result["spoof_probability"]
    assert 0.0 <= prob <= 1.0, "Probability must be between 0 and 1"
