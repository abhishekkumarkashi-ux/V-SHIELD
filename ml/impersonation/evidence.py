from dataclasses import dataclass
from typing import Optional

@dataclass
class EvidenceModel:
    spoof_probability: float
    speaker_similarity: Optional[float]
    speaker_status: str  # 'VERIFIED', 'NOT_VERIFIED', 'NOT_ENROLLED', 'INSUFFICIENT_AUDIO', 'ERROR'
    vad_status: str      # 'SPEECH', 'SILENCE'
    
    @property
    def is_suspicious_spoof(self) -> bool:
        return self.spoof_probability > 0.6
        
    @property
    def is_suspicious_speaker(self) -> bool:
        if self.speaker_similarity is None:
            return False
        # Cosine similarity typically > 0.25 for same speaker in ECAPA-TDNN
        return self.speaker_similarity < 0.25
