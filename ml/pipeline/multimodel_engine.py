import time
import os
import yaml
import torch
import numpy as np

from ml.models.aasist.loader import AASISTLoader
from ml.models.wavlm.loader import WavLMLoader
from ml.models.ecapa.loader import ECAPALoader
from ml.models.fusion.fusion_model import MultiModelFusionHead
from ml.pipeline.preprocessing import sanitize_and_prepare_audio

# Attempt to load the existing risk engine calculation for final aggregation
try:
    from ml.src.risk_score import calculate_risk_score
except ImportError:
    def calculate_risk_score(prob):
        return {"impersonation_risk_score": int(prob * 100), "impersonation_risk_level": "HIGH" if prob > 0.8 else "LOW"}

class MultiModelEngine:
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to repo location
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(base_dir, "ml", "config", "multimodel.yaml")
            
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
            
        self.aasist_loader = AASISTLoader(self.config["models"]["aasist"])
        self.wavlm_loader = WavLMLoader(self.config["models"]["wavlm"])
        self.ecapa_loader = ECAPALoader(self.config["models"]["ecapa"])
        
        # Fusion head logic
        self.fusion_head = MultiModelFusionHead(
            input_dim=self.config["models"]["fusion"]["input_dim"],
            hidden_dim=self.config["models"]["fusion"]["hidden_dim"],
            dropout=self.config["models"]["fusion"]["dropout"]
        )
        self.fusion_status = "NOT_CONFIGURED"
        self.is_loaded = False
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
    def load_models(self):
        print("[V-SHIELD] Loading Multi-Model Engine...")
        self.aasist_loader.load(self.config["models"]["aasist"].get("checkpoint", ""))
        self.wavlm_loader.load()
        self.ecapa_loader.load()
        
        # Load fusion checkpoint if available
        fusion_ckpt = self.config["models"]["fusion"].get("checkpoint", "")
        if os.path.exists(fusion_ckpt):
            try:
                state = torch.load(fusion_ckpt, map_location=self.device)
                self.fusion_head.load_state_dict(state)
                self.fusion_status = "READY"
            except Exception as e:
                self.fusion_status = "ERROR"
                print(f"Failed to load fusion weights: {e}")
        else:
            self.fusion_status = "UNTRAINED_FOR_VSHIELD"
            
        self.fusion_head.to(self.device)
        self.fusion_head.eval()
        self.is_loaded = True
        print("[V-SHIELD] Multi-Model Engine loading complete.")
        
    def get_status(self):
        return {
            "aasist": self.aasist_loader.model_status,
            "wavlm": self.wavlm_loader.model_status,
            "ecapa": self.ecapa_loader.model_status,
            "fusion": self.fusion_status,
            "overall_ready": all(s in ["READY", "PRETRAINED_BASELINE", "UNTRAINED_FOR_VSHIELD"] for s in [
                self.aasist_loader.model_status, 
                self.wavlm_loader.model_status, 
                self.ecapa_loader.model_status
            ])
        }
        
    def analyze(self, audio_chunk: np.ndarray, enrolled_embedding=None):
        """
        Runs the full multimodel pipeline.
        Args:
            audio_chunk: 1D np.ndarray, 16kHz float32
            enrolled_embedding: optional enrolled ECAPA embedding
        """
        if not self.is_loaded:
            return {"error": "MultiModelEngine not loaded. Call load_models() first."}
            
        tensor = sanitize_and_prepare_audio(audio_chunk, self.config["runtime"]["window_samples"])
        
        result = {
            "model_status": self.get_status(),
            "aasist": {},
            "wavlm": {},
            "ecapa": {},
            "fusion": {},
            "latency": {}
        }
        
        total_start = time.time()
        
        # 1. AASIST
        t0 = time.time()
        aasist_emb = None
        aasist_spoof_prob = 0.5
        if self.aasist_loader.is_loaded:
            try:
                aasist_emb = self.aasist_loader.extract_embedding(tensor)
                probs = self.aasist_loader.predict_spoof(tensor)
                aasist_spoof_prob = probs["spoof_probability"]
                result["aasist"] = {"spoof_probability": aasist_spoof_prob, "embedding_shape": list(aasist_emb.shape)}
            except Exception as e:
                result["aasist"] = {"error": str(e)}
        result["latency"]["aasist_ms"] = int((time.time() - t0) * 1000)
                
        # 2. WavLM
        t0 = time.time()
        wavlm_emb = None
        if self.wavlm_loader.is_loaded:
            try:
                wavlm_emb = self.wavlm_loader.extract_embedding(tensor)
                result["wavlm"] = {"embedding_shape": list(wavlm_emb.shape)}
            except Exception as e:
                result["wavlm"] = {"error": str(e)}
        result["latency"]["wavlm_ms"] = int((time.time() - t0) * 1000)
                
        # 3. ECAPA
        t0 = time.time()
        ecapa_emb = None
        speaker_sim = None
        if self.ecapa_loader.is_loaded:
            try:
                ecapa_emb = self.ecapa_loader.extract_embedding(tensor)
                result["ecapa"]["embedding_shape"] = list(ecapa_emb.shape)
                if enrolled_embedding is not None:
                    speaker_sim = self.ecapa_loader.compute_similarity(enrolled_embedding, ecapa_emb)
                    result["ecapa"]["speaker_similarity"] = speaker_sim
            except Exception as e:
                result["ecapa"] = {"error": str(e)}
        result["latency"]["ecapa_ms"] = int((time.time() - t0) * 1000)
                
        # 4. Fusion
        t0 = time.time()
        fusion_spoof_prob = aasist_spoof_prob # Fallback if fusion is untrained
        
        if self.fusion_status in ["READY", "UNTRAINED_FOR_VSHIELD"]:
            try:
                # Mock or provide zeros for missing embeddings to keep dimensions stable
                _a = aasist_emb if aasist_emb is not None else torch.zeros(1, 160).to(self.device)
                _w = wavlm_emb if wavlm_emb is not None else torch.zeros(1, 768).to(self.device)
                _e = ecapa_emb if ecapa_emb is not None else torch.zeros(1, 192).to(self.device)
                _sp = torch.tensor([[aasist_spoof_prob]], dtype=torch.float32).to(self.device)
                _ss = torch.tensor([[speaker_sim if speaker_sim is not None else 0.0]], dtype=torch.float32).to(self.device)
                
                with torch.inference_mode():
                    fusion_out = self.fusion_head(_a, _w, _e, _sp, _ss)
                
                result["fusion"] = {k: v.item() for k, v in fusion_out.items()}
                
                if self.fusion_status == "READY":
                    fusion_spoof_prob = fusion_out["spoof_probability"].item()
                    
            except Exception as e:
                result["fusion"] = {"error": str(e)}
        result["latency"]["fusion_ms"] = int((time.time() - t0) * 1000)
        
        # 5. Final Risk Engine
        risk = calculate_risk_score(fusion_spoof_prob)
        result["risk"] = risk
        
        result["latency"]["total_ms"] = int((time.time() - total_start) * 1000)
        
        return result

# Global singleton
multimodel_instance = MultiModelEngine()
