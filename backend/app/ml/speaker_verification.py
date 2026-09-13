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
            # Using torch cosine similarity
            if isinstance(emb1, dict) or isinstance(emb2, dict):
                return -1.0 # Error state
                
            # Squeeze to 1D or 2D and compute
            sim = torch.nn.functional.cosine_similarity(
                emb1.squeeze(1), emb2.squeeze(1), dim=-1
            )
            return sim.item()
        except Exception as e:
            traceback.print_exc()
            return -1.0

speaker_verification_instance = SpeakerVerificationModel()
