import torch
from .model import WavLMWrapper

class WavLMLoader:
    def __init__(self, config=None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.config = config or {}
        self.model = None
        self.is_loaded = False
        self.model_status = "NOT_CONFIGURED"
        
    def load(self):
        enabled = self.config.get("enabled", True)
        if not enabled:
            self.model_status = "DISABLED"
            self.is_loaded = False
            return False
            
        try:
            self.model_status = "LOADING"
            model_name = self.config.get("model_name", "microsoft/wavlm-base-plus")
            freeze = self.config.get("freeze", True)
            
            self.model = WavLMWrapper(model_name=model_name, freeze=freeze).to(self.device)
            self.model.eval()
            self.is_loaded = True
            self.model_status = "READY"
            
            return True
            
        except Exception as e:
            self.model_status = "ERROR"
            self.is_loaded = False
            print(f"Failed to load WavLM: {e}")
            return False
            
    def extract_embedding(self, audio_tensor):
        if not self.is_loaded or self.model is None:
            raise RuntimeError(f"WavLM is not loaded. Status: {self.model_status}")
            
        with torch.inference_mode():
            audio_tensor = audio_tensor.to(self.device)
            _, pooled = self.model(audio_tensor)
            return pooled

    def extract_features(self, audio_tensor):
        if not self.is_loaded or self.model is None:
            raise RuntimeError(f"WavLM is not loaded. Status: {self.model_status}")
            
        with torch.inference_mode():
            audio_tensor = audio_tensor.to(self.device)
            hidden_states, _ = self.model(audio_tensor)
            return hidden_states
