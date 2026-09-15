import os
import torch
import torchaudio
import traceback
import sys

# Ensure speechbrain is installed
try:
    from speechbrain.inference.speaker import SpeakerRecognition
except ImportError:
    print("WARNING: speechbrain not installed. Speaker verification will be disabled.")
    SpeakerRecognition = None

class SpeakerVerificationModel:
    def __init__(self):
        self.is_loaded = False
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        
    def load_model(self):
        if SpeakerRecognition is None:
            return False
            
        try:
            self.model = SpeakerRecognition.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb", 
                run_opts={"device": str(self.device)}
            )
            self.is_loaded = True
            print(f"[V-SHIELD] Speaker Verification Model successfully loaded on {self.device}")
            return True
        except Exception as e:
            print(f"Failed to load speaker verification model: {e}")
            traceback.print_exc()
            return False

    def extract_embedding(self, pcm_data):
        """
        Extracts a speaker embedding from a raw 16kHz float32 PCM array.
        """
        if not self.is_loaded or self.model is None:
            return {"error": "Model not loaded"}
            
        try:
            waveform = torch.tensor(pcm_data, dtype=torch.float32).unsqueeze(0).to(self.device)
            # Embeddings are typically 1x1x192
            embedding = self.model.encode_batch(waveform)
            return {"embedding": embedding}
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}

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

speaker_verification_instance = SpeakerVerificationModel()
