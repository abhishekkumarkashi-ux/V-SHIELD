import torch
import numpy as np

def sanitize_and_prepare_audio(audio_chunk: np.ndarray, max_length: int = 64000) -> torch.Tensor:
    """
    Ensures audio meets the 16kHz Mono Float32 64000-sample contract.
    """
    if not isinstance(audio_chunk, np.ndarray):
        audio_chunk = np.array(audio_chunk, dtype=np.float32)
        
    # Replace non-finite with 0
    audio_chunk = np.nan_to_num(audio_chunk, nan=0.0, posinf=0.0, neginf=0.0)
    
    waveform = torch.tensor(audio_chunk, dtype=torch.float32)
    
    # Enforce Mono
    if waveform.dim() > 1:
        if waveform.shape[0] > 1 and waveform.shape[1] > 1:
            # Attempt to mean over channels
            if waveform.shape[0] < waveform.shape[1]:
                waveform = torch.mean(waveform, dim=0)
            else:
                waveform = torch.mean(waveform, dim=1)
        else:
            waveform = waveform.squeeze()

    # Enforce length
    if waveform.shape[0] < max_length:
        padding = max_length - waveform.shape[0]
        waveform = torch.nn.functional.pad(waveform, (0, padding))
    else:
        waveform = waveform[:max_length]
        
    # Peak normalization
    max_val = torch.max(torch.abs(waveform))
    if max_val > 0:
        waveform = waveform / max_val
        
    # Final shape for models: (1, 64000)
    return waveform.unsqueeze(0)
