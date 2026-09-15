import torch
import torch.nn as nn

class FeatureFusion(nn.Module):
    """
    Fuses features from multiple models.
    Concatenates embeddings and scalars, then applies a trainable projection network.
    """
    def __init__(self, input_dim=1122, hidden_dim=512, dropout=0.3):
        super(FeatureFusion, self).__init__()
        
        self.network = nn.Sequential(
            nn.LayerNorm(input_dim),
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout)
        )
        
        self.output_dim = hidden_dim // 2
        
    def forward(self, aasist_emb, wavlm_emb, ecapa_emb, spoof_prob, speaker_sim):
        """
        Args:
            aasist_emb: (batch, 160)
            wavlm_emb: (batch, 768)
            ecapa_emb: (batch, 192)
            spoof_prob: (batch, 1)
            speaker_sim: (batch, 1)
        """
        # Ensure all are 2D tensors (batch, dim)
        def _ensure_2d(t):
            if t is None:
                return None
            if t.dim() == 1:
                return t.unsqueeze(1)
            if t.dim() > 2:
                return t.view(t.shape[0], -1)
            return t
            
        aasist_emb = _ensure_2d(aasist_emb)
        wavlm_emb = _ensure_2d(wavlm_emb)
        ecapa_emb = _ensure_2d(ecapa_emb)
        spoof_prob = _ensure_2d(spoof_prob)
        speaker_sim = _ensure_2d(speaker_sim)
        
        features = []
        if aasist_emb is not None: features.append(aasist_emb)
        if wavlm_emb is not None: features.append(wavlm_emb)
        if ecapa_emb is not None: features.append(ecapa_emb)
        if spoof_prob is not None: features.append(spoof_prob)
        if speaker_sim is not None: features.append(speaker_sim)
        
        fused_vector = torch.cat(features, dim=1)
        return self.network(fused_vector)
