from typing import List, Tuple
from .evidence import EvidenceModel
from .temporal import TemporalHistory
from .config import TEMPORAL_ESCALATION_THRESHOLD, RISK_LOW_THRESHOLD, RISK_MEDIUM_THRESHOLD, RISK_HIGH_THRESHOLD

class DecisionMaker:
    def evaluate(self, current_evidence: EvidenceModel, history: TemporalHistory, smoothed_spoof: float) -> Tuple[float, str, str, List[str]]:
        reasons = []
        base_risk = 0.0
        
        # 1. Base states and reasons
        if current_evidence.speaker_status == "NOT_ENROLLED":
            if smoothed_spoof > 0.6:
                base_risk = smoothed_spoof * 100
                reasons.append("High synthetic-voice probability")
            else:
                base_risk = smoothed_spoof * 100
            reasons.append("Speaker verification unavailable")
                
        elif current_evidence.speaker_status in ["VERIFIED", "VERIFYING"]:
            if smoothed_spoof > 0.6:
                base_risk = smoothed_spoof * 100
                reasons.append("Suspicious synthetic/manipulated voice signal")
            else:
                base_risk = smoothed_spoof * 100
                
        elif current_evidence.speaker_status == "NOT_VERIFIED":
            if smoothed_spoof > 0.6:
                base_risk = max(85.0, smoothed_spoof * 100)
                reasons.append("Strong impersonation evidence")
                reasons.append("Low similarity to enrolled speaker")
                reasons.append("High synthetic-voice probability")
            else:
                base_risk = max(70.0, smoothed_spoof * 100)
                reasons.append("Possible speaker mismatch")
                reasons.append("Low similarity to enrolled speaker")
                
        elif current_evidence.speaker_status == "INSUFFICIENT_AUDIO":
            base_risk = smoothed_spoof * 100
            reasons.append("Audio too short for reliable verification")
            
        else:
            base_risk = smoothed_spoof * 100
            
        # 2. Temporal Persistence Adjustments
        persistence = history.get_persistence_ratio()
        if history.get_recent_suspicious_count(TEMPORAL_ESCALATION_THRESHOLD) >= TEMPORAL_ESCALATION_THRESHOLD:
            base_risk = min(100.0, base_risk + (15.0 * persistence))
            reasons.append("Suspicious evidence persisted across multiple windows")
            
        # 3. Confidence Assessment
        confidence = "HIGH"
        if len(history.windows) < 3 or current_evidence.speaker_status == "INSUFFICIENT_AUDIO":
            confidence = "LOW"
        elif len(history.windows) < 10:
            confidence = "MEDIUM"
            
        # Ensure clamped
        final_risk = max(0.0, min(100.0, base_risk))
        
        # Risk Level
        if final_risk >= RISK_HIGH_THRESHOLD:
            level = "CRITICAL"
        elif final_risk >= RISK_MEDIUM_THRESHOLD:
            level = "HIGH"
        elif final_risk >= RISK_LOW_THRESHOLD:
            level = "MEDIUM"
        else:
            level = "LOW"
            
        return final_risk, level, confidence, reasons
