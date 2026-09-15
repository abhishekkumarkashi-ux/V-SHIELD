import os
import sys
import torch
import io
import soundfile as sf
import traceback

# Add V-SHIELD/ml to path
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ml_src_dir = os.path.join(base_dir, 'ml', 'src')
sys.path.append(ml_src_dir)

try:
    from ml.models.baseline.lightweight_cnn import LightweightAntiSpoofCNN
    from risk_score import calculate_risk_score
except ImportError as e:
    print(f"WARNING: Could not import ml modules. Ensure PYTHONPATH is correct. Error: {e}")

import json

class VoiceAntiSpoofModel:
    def __init__(self):
        self.is_loaded = False
        self.model_status = "NOT_LOADED"
        self.production_ready = False
        self.validation_status = "UNKNOWN"
        self.disclaimer = "Anti-spoofing model has not been loaded."
        self.model_disclaimer = self.disclaimer
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.max_length = 16000 * 4 # 4 seconds
        
    def load_model(self, model_path: str):
        if not os.path.exists(model_path):
            print(f"Model path does not exist: {model_path}")
            self.model_status = "MISSING"
            return False
            
        try:
            self.model = LightweightAntiSpoofCNN()
            state_dict = torch.load(model_path, map_location=self.device, weights_only=True)
            self.model.load_state_dict(state_dict)
            self.model.to(self.device)
            self.model.eval()
            self.is_loaded = True
            
            # Check for model metadata
            meta_path = os.path.join(os.path.dirname(model_path), "model_meta.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r") as mf:
                        meta = json.load(mf)
                        self.model_status = meta.get("status", "UNTRAINED")
                        self.production_ready = meta.get("production_ready", False)
                        self.validation_status = meta.get("validation_status", "DEVELOPMENT_ONLY")
                        self.disclaimer = meta.get("disclaimer", "Anti-spoofing model is not validated for production use.")
                except Exception:
                    self.model_status = "UNTRAINED"
                    self.production_ready = False
                    self.disclaimer = "Anti-spoofing model is not validated for production use."
            else:
                self.model_status = "UNTRAINED"
                self.production_ready = False
                self.disclaimer = "Anti-spoofing model is not validated for production use."
            self.model_disclaimer = self.disclaimer
                
            print(f"[V-SHIELD] Model loaded on {self.device}. Status: {self.model_status}, Production ready: {self.production_ready}")
            print(f"[V-SHIELD] Model path: {model_path}")
            return True
        except Exception as e:
            self.model_status = "CORRUPTED"
            self.is_loaded = False
            print(f"Failed to load model: {e}")
            return False
            
    def predict(self, audio_bytes: bytes) -> dict:
        if not self.is_loaded:
            return {"error": "Model not loaded"}
            
        try:
            # 1. Load audio from bytes using soundfile
            audio_file = io.BytesIO(audio_bytes)
            wav, sr = sf.read(audio_file)
            
            # 2. Resample / Mono conversion (naive assumption 16k mono for now if using sf.read directly)
            waveform = torch.tensor(wav, dtype=torch.float32)
            if waveform.dim() == 1:
                waveform = waveform.unsqueeze(0)
            else:
                waveform = waveform.t()
            
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
                
            # Truncate / Pad
            if waveform.shape[1] < self.max_length:
                padding = self.max_length - waveform.shape[1]
                waveform = torch.nn.functional.pad(waveform, (0, padding))
            else:
                waveform = waveform[:, :self.max_length]
                
            # Normalize
            max_val = torch.max(torch.abs(waveform))
            if max_val > 0:
                waveform = waveform / max_val
                
            waveform = waveform.unsqueeze(0).to(self.device) # Batch dimension
            
            # 3. Model Inference
            with torch.inference_mode():
                logits = self.model(waveform)
                prob = torch.sigmoid(logits).item()
                
            # 4. Map to Risk Score
            return calculate_risk_score(prob)
            
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Inference failed: {str(e)}"}

    def predict_pcm(self, pcm_data) -> dict:
        if not self.is_loaded:
            return {"error": "Model not loaded"}
            
        try:
            # pcm_data is a 1D numpy array of float32
            import torch
            waveform = torch.tensor(pcm_data, dtype=torch.float32).unsqueeze(0) # [1, L]
            
            # Truncate / Pad
            if waveform.shape[1] < self.max_length:
                padding = self.max_length - waveform.shape[1]
                waveform = torch.nn.functional.pad(waveform, (0, padding))
            else:
                waveform = waveform[:, :self.max_length]
                
            # Normalize
            max_val = torch.max(torch.abs(waveform))
            if max_val > 0:
                waveform = waveform / max_val
                
            waveform = waveform.unsqueeze(0).to(self.device) # Batch dimension
            
            # 3. Model Inference
            with torch.inference_mode():
                logits = self.model(waveform)
                prob = torch.sigmoid(logits).item()
                
            # We don't apply calculate_risk_score here for WebSocket streams because they need stateful EMA.
            # So we return the raw prob.
            return {"spoof_probability": prob}
            
        except Exception as e:
            traceback.print_exc()
            return {"error": f"PCM Inference failed: {str(e)}"}

# Global instance for the application
model_instance = VoiceAntiSpoofModel()
