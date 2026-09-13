from collections import deque
from .config import MAX_HISTORY_WINDOWS
from .evidence import EvidenceModel

class TemporalHistory:
    def __init__(self):
        self.windows = deque(maxlen=MAX_HISTORY_WINDOWS)
        
    def add_evidence(self, evidence: EvidenceModel):
        if evidence.vad_status == 'SPEECH':
            self.windows.append(evidence)
            
    def get_smoothed_spoof_probability(self) -> float:
        if not self.windows:
            return 0.0
        # Simple EMA over the bounded history
        alpha = 0.3
        smoothed = self.windows[0].spoof_probability
        for w in list(self.windows)[1:]:
            smoothed = (alpha * w.spoof_probability) + ((1 - alpha) * smoothed)
        return smoothed
        
    def get_recent_suspicious_count(self, n=5) -> int:
        recent = list(self.windows)[-n:]
        count = sum(1 for w in recent if w.is_suspicious_spoof or w.is_suspicious_speaker)
        return count
        
    def get_recent_safe_count(self, n=5) -> int:
        recent = list(self.windows)[-n:]
        count = sum(1 for w in recent if not w.is_suspicious_spoof and not w.is_suspicious_speaker)
        return count
        
    def get_persistence_ratio(self) -> float:
        if not self.windows:
            return 0.0
        suspicious = sum(1 for w in self.windows if w.is_suspicious_spoof or w.is_suspicious_speaker)
        return suspicious / len(self.windows)
