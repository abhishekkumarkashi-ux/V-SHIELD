import torch
import traceback
from .model import ECAPAModel

class ECAPALoader:
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
            source = self.config.get("source", "speechbrain/spkrec-ecapa-voxceleb")
            
            self.model = ECAPAModel(source=source, device=str(self.device))
            self.model.eval()
            self.is_loaded = True
            self.model_status = "READY"
            
            return True
            
        except Exception as e:
            self.model_status = "ERROR"
            self.is_loaded = False
            print(f"Failed to load ECAPA-TDNN: {e}")
            return False
            
    def extract_embedding(self, audio_tensor):
        if not self.is_loaded or self.model is None:
            raise RuntimeError(f"ECAPA-TDNN is not loaded. Status: {self.model_status}")
            
        with torch.inference_mode():
            audio_tensor = audio_tensor.to(self.device)
            embedding = self.model(audio_tensor)
            return embedding

    def compute_similarity(self, emb1, emb2) -> float:
        """
        Computes cosine similarity between two embeddings.
        Returns a float between -1.0 and 1.0.
        """
        try:
            if isinstance(emb1, dict) or isinstance(emb2, dict) or emb1 is None or emb2 is None:
                return -1.0

            import numpy as np
            if isinstance(emb1, np.ndarray):
                emb1 = torch.from_numpy(emb1)
            elif not isinstance(emb1, torch.Tensor):
                emb1 = torch.tensor(emb1)

            if isinstance(emb2, np.ndarray):
                emb2 = torch.from_numpy(emb2)
            elif not isinstance(emb2, torch.Tensor):
                emb2 = torch.tensor(emb2)

            emb1 = emb1.to(device=self.device, dtype=torch.float32)
            emb2 = emb2.to(device=self.device, dtype=torch.float32)

            if emb1.dim() > 2:
                emb1 = emb1.squeeze(1)
            if emb2.dim() > 2:
                emb2 = emb2.squeeze(1)

            sim = torch.nn.functional.cosine_similarity(emb1, emb2, dim=-1)
            return float(sim.mean().item())
        except Exception as e:
            traceback.print_exc()
            return -1.0
