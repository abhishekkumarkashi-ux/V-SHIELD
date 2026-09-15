import os
import torch
from .model import AASIST

class AASISTLoader:
    def __init__(self, config=None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.config = config or {}
        self.model = None
        self.is_loaded = False
        self.model_status = "NOT_CONFIGURED"
        
    def load(self, checkpoint_path: str):
        if not os.path.exists(checkpoint_path):
            self.model_status = "MODEL_NOT_AVAILABLE"
            self.is_loaded = False
            return False
            
        try:
            self.model_status = "LOADING"
            # Initialize AASIST architecture
            # The config dictionary should match the one expected by AASIST.
            # Using default ASVspoof 2019 parameters for AASIST.
            aasist_config = {
                "architecture": "AASIST",
                "filter_length": 128,
                "nb_samp": 64000,
                "first_conv": 128,
                "filts": [70, [1, 32], [32, 32], [32, 64], [64, 64]],
                "gat_dims": [64, 32],
                "pool_ratios": [0.5, 0.7, 0.5, 0.5],
                "temperatures": [2.0, 2.0, 100.0, 100.0]
            }
            
            self.model = AASIST(aasist_config).to(self.device)
            
            # Load weights
            state_dict = torch.load(checkpoint_path, map_location=self.device, weights_only=True)
            self.model.load_state_dict(state_dict)
            self.model.eval()
            self.is_loaded = True
            self.model_status = "READY"
            
            # Check metadata
            meta_path = os.path.join(os.path.dirname(checkpoint_path), "model_meta.json")
            if not os.path.exists(meta_path):
                self.model_status = "PRETRAINED_BASELINE"
            
            return True
            
        except Exception as e:
            self.model_status = "ERROR"
            self.is_loaded = False
            print(f"Failed to load AASIST: {e}")
            return False
            
    def extract_embedding(self, audio_tensor):
        if not self.is_loaded or self.model is None:
            raise RuntimeError(f"AASIST is not loaded. Status: {self.model_status}")
            
        with torch.inference_mode():
            # audio_tensor expected: (batch, 1, 64000) or (batch, 64000)
            if audio_tensor.dim() == 3:
                audio_tensor = audio_tensor.squeeze(1)
            audio_tensor = audio_tensor.to(self.device)
            _, embedding = self.model(audio_tensor)
            return embedding
            
    def predict_spoof(self, audio_tensor):
        if not self.is_loaded or self.model is None:
            raise RuntimeError(f"AASIST is not loaded. Status: {self.model_status}")
            
        with torch.inference_mode():
            if audio_tensor.dim() == 3:
                audio_tensor = audio_tensor.squeeze(1)
            audio_tensor = audio_tensor.to(self.device)
            logits, _ = self.model(audio_tensor)
            
            # AASIST outputs logits for [bonafide, spoof]. 
            # We apply softmax and extract spoof probability (index 1).
            probs = torch.softmax(logits, dim=-1)
            return {
                "bonafide_probability": probs[0, 0].item(),
                "spoof_probability": probs[0, 1].item()
            }
