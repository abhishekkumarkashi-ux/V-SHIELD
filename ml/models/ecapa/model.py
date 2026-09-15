import torch
import torch.nn as nn
import traceback

try:
    from speechbrain.inference.speaker import SpeakerRecognition
except ImportError:
    SpeakerRecognition = None

class ECAPAModel(nn.Module):
    """Wrapper around SpeechBrain ECAPA-TDNN for speaker verification."""
    def __init__(self, source="speechbrain/spkrec-ecapa-voxceleb", device="cpu"):
        super(ECAPAModel, self).__init__()
        
        if SpeakerRecognition is None:
            raise RuntimeError("speechbrain is not installed. ECAPA-TDNN cannot be loaded.")
            
        self.model = SpeakerRecognition.from_hparams(
            source=source, 
            run_opts={"device": device}
        )
        
    def forward(self, x):
        """
        Extracts speaker embeddings.
        Args:
            x: (batch, samples) audio tensor at 16kHz
        Returns:
            embedding: (batch, 1, 192)
        """
        # SpeechBrain expects (batch, samples)
        if x.dim() == 3:
            x = x.squeeze(1)
            
        return self.model.encode_batch(x)
