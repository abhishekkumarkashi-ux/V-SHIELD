import yaml
import os

def load_config():
    # Attempt to load config relative to the current file
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, 'config.yaml')
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}

config = load_config()

class RiskScoreEngine:
    def __init__(self):
        risk_cfg = config.get('risk', {})
        self.low_max = risk_cfg.get('low_max', 29)
        self.medium_max = risk_cfg.get('medium_max', 59)
        self.high_max = risk_cfg.get('high_max', 79)
        
        smoothing_cfg = risk_cfg.get('smoothing', {})
        self.smoothing_enabled = smoothing_cfg.get('enabled', True)
        self.alpha = smoothing_cfg.get('alpha', 0.3)
        
        self.ema_score = None
        
    def reset(self):
        """Resets the EMA smoothing state for a new call/stream."""
        self.ema_score = None

    def calculate_risk_score(self, spoof_probability: float) -> dict:
        """
        Maps a continuous spoof_probability (0.0 - 1.0) to a V-SHIELD Risk Score (0-100).
        IMPORTANT: This is a V1 prototype risk score, not a clinically/security-certified probability of impersonation.
        """
        # 1. Clamp spoof probability to 0.0 - 1.0
        clamped_prob = max(0.0, min(1.0, float(spoof_probability)))
        
        # 2. Map to 0 - 100 risk score
        current_chunk_score = int(round(clamped_prob * 100))
        
        # 3. Apply Temporal Smoothing (EMA) if enabled
        if self.smoothing_enabled:
            if self.ema_score is None:
                self.ema_score = float(current_chunk_score)
            else:
                self.ema_score = (self.alpha * current_chunk_score) + ((1.0 - self.alpha) * self.ema_score)
            
            final_score = int(round(self.ema_score))
        else:
            final_score = current_chunk_score
            self.ema_score = float(current_chunk_score)
            
        # 4. Determine Risk Level
        if final_score <= self.low_max:
            risk_level = "LOW"
        elif final_score <= self.medium_max:
            risk_level = "MEDIUM"
        elif final_score <= self.high_max:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"
            
        prediction = "spoof" if final_score > 50 else "bonafide"

        return {
            "prediction": prediction,
            "spoof_probability": float(round(clamped_prob, 4)),
            "current_chunk_score": current_chunk_score,
            "smoothed_score": float(round(self.ema_score, 2)),
            "risk_score": final_score,
            "risk_level": risk_level,
            "warning": "V1 prototype risk score - not a certified probability of impersonation."
        }

# Global instance for single-file analysis
default_engine = RiskScoreEngine()

def calculate_risk_score(spoof_probability: float) -> dict:
    """Wrapper for single-shot evaluations using default config."""
    return default_engine.calculate_risk_score(spoof_probability)
