import torch
import torch.nn as nn
from .feature_fusion import FeatureFusion

class MultiModelFusionHead(nn.Module):
    """
    Final fusion head that takes fused features and produces distinct security scores.
    """
    def __init__(self, input_dim=1122, hidden_dim=512, dropout=0.3):
        super(MultiModelFusionHead, self).__init__()
        
        self.feature_fusion = FeatureFusion(input_dim=input_dim, hidden_dim=hidden_dim, dropout=dropout)
        
        fused_dim = self.feature_fusion.output_dim
        
        # We output three separate scores
        self.classifier = nn.Linear(fused_dim, 3)
        
    def forward(self, aasist_emb, wavlm_emb, ecapa_emb, spoof_prob, speaker_sim):
        fused_features = self.feature_fusion(aasist_emb, wavlm_emb, ecapa_emb, spoof_prob, speaker_sim)
        logits = self.classifier(fused_features)
        
        probs = torch.sigmoid(logits)
        
        # Map to specific outputs
        return {
            "spoof_probability": probs[:, 0],
            "speaker_mismatch_probability": probs[:, 1],
            "combined_security_score": probs[:, 2] # Higher means more secure
        }
