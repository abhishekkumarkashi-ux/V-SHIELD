import time
from typing import Dict, Any
from .config import ALERT_COOLDOWN_SECONDS
from .evidence import EvidenceModel
from .temporal import TemporalHistory
from .decision import DecisionMaker

class ImpersonationEngine:
    def __init__(self):
        self.history = TemporalHistory()
        self.decision_maker = DecisionMaker()
        self.last_alert_time = 0.0
        
    def reset(self):
        self.history = TemporalHistory()
        self.last_alert_time = 0.0
        
    def process_window(self, 
                       spoof_probability: float, 
                       speaker_similarity: float = None, 
                       speaker_enrolled: bool = False) -> Dict[str, Any]:
                       
        import math
        
        # Validation
        if math.isnan(spoof_probability) or math.isinf(spoof_probability):
            raise ValueError("Invalid spoof_probability")
        if speaker_similarity is not None and (math.isnan(speaker_similarity) or math.isinf(speaker_similarity)):
            raise ValueError("Invalid speaker_similarity")
            
        spoof_probability = max(0.0, min(1.0, float(spoof_probability)))
        if speaker_similarity is not None:
            speaker_similarity = max(-1.0, min(1.0, float(speaker_similarity)))
                       
        # Determine speaker status
        if not speaker_enrolled:
            speaker_status = "NOT_ENROLLED"
        elif speaker_similarity is None:
            speaker_status = "INSUFFICIENT_AUDIO"
        else:
            if speaker_similarity >= 0.25:
                speaker_status = "VERIFIED"
            else:
                speaker_status = "NOT_VERIFIED"
                
        # Create evidence model
        evidence = EvidenceModel(
            spoof_probability=float(spoof_probability),
            speaker_similarity=float(speaker_similarity) if speaker_similarity is not None else None,
            speaker_status=speaker_status,
            vad_status="SPEECH"
        )
        
        self.history.add_evidence(evidence)
        smoothed_spoof = self.history.get_smoothed_spoof_probability()
        
        # Make decision
        risk_score, risk_level, confidence, reasons = self.decision_maker.evaluate(
            evidence, self.history, smoothed_spoof
        )
        
        # Alert mechanism
        alert_event = None
        if risk_level in ["HIGH", "CRITICAL"] and confidence in ["MEDIUM", "HIGH"]:
            current_time = time.time()
            if (current_time - self.last_alert_time) > ALERT_COOLDOWN_SECONDS:
                alert_event = {
                    "event": "IMPERSONATION_RISK",
                    "severity": risk_level,
                    "score": round(risk_score, 1),
                    "reasons": reasons
                }
                self.last_alert_time = current_time
                
        # Payload
        payload = {
            "spoof_probability": float(spoof_probability),
            "spoof_probability_smoothed": float(smoothed_spoof),
            "speaker_similarity": float(speaker_similarity) if speaker_similarity is not None else None,
            "speaker_status": speaker_status,
            "impersonation_risk_score": round(risk_score, 1),
            "impersonation_risk_level": risk_level,
            "risk_confidence": confidence,
            "risk_reasons": reasons,
            "timestamp": time.time()
        }
        
        if alert_event:
            payload["alert"] = alert_event
            
        return payload
