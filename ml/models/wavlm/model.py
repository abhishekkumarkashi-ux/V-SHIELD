import torch
import torch.nn as nn

try:
    from transformers import WavLMModel
except ImportError:
    WavLMModel = None

class WavLMWrapper(nn.Module):
    """Wrapper around Hugging Face WavLM for feature extraction."""
    def __init__(self, model_name="microsoft/wavlm-base-plus", freeze=True):
        super(WavLMWrapper, self).__init__()
        
        if WavLMModel is None:
            raise RuntimeError("transformers library is not installed. WavLM cannot be loaded.")
            
        self.wavlm = WavLMModel.from_pretrained(model_name)
        
        # Freeze weights if requested
        if freeze:
            for param in self.wavlm.parameters():
                param.requires_grad = False
                
    def forward(self, x):
        """
        Forward pass for WavLM.
        Args:
            x: (batch, samples) audio tensor at 16kHz
        Returns:
            hidden_states: (batch, frames, hidden_size)
            pooled_output: (batch, hidden_size) Mean-pooled across time.
        """
        if x.dim() == 3:
            x = x.squeeze(1) # Remove channel dim
            
        outputs = self.wavlm(x, output_hidden_states=True)
        # Use the last hidden state for representations
        hidden_states = outputs.last_hidden_state
        
        # Mean pool over time dimension (dim=1) for a single embedding
        pooled_output = torch.mean(hidden_states, dim=1)
        
        return hidden_states, pooled_output
