class RiskEngine:
    def __init__(self, alpha=0.3):
        self.alpha = alpha
        self.current_risk = 0.0
        
    def reset(self):
        self.current_risk = 0.0
        
    def calculate_risk_score(self, spoof_probability: float, speaker_similarity: float = None) -> dict:
        """
        Calculates the overall risk score using an Exponential Moving Average (EMA).
        Incorporates speaker similarity to flag imposters.
        """
        if self.current_risk == 0.0:
            self.current_risk = spoof_probability
        else:
            self.current_risk = (self.alpha * spoof_probability) + ((1 - self.alpha) * self.current_risk)
            
        # Factor in speaker similarity
        imposter_warning = False
        if speaker_similarity is not None:
            # Cosine similarity typically > 0.25 for same speaker in ECAPA-TDNN
            if speaker_similarity < 0.25:
                imposter_warning = True
                # Boost risk if imposter detected
                self.current_risk = max(self.current_risk, 0.85)
            
        risk_level = "LOW"
        if self.current_risk > 0.8:
            risk_level = "CRITICAL"
        elif self.current_risk > 0.6:
            risk_level = "HIGH"
        elif self.current_risk > 0.4:
            risk_level = "MEDIUM"
            
        return {
            "risk_score": float(self.current_risk),
            "risk_level": risk_level,
            "imposter_warning": imposter_warning,
            "speaker_similarity": float(speaker_similarity) if speaker_similarity is not None else None
        }

risk_engine_instance = RiskEngine()
