"""
Audio Preprocessing for V-SHIELD.
Ensures mathematical consistency between training and backend inference.
"""

import torch
import torch.nn.functional as F
import numpy as np

WINDOW_SAMPLES = 64000  # 4.0 seconds at 16kHz

def sanitize_waveform(waveform: torch.Tensor) -> torch.Tensor:
    """Replaces NaNs or Infs with zero."""
    if not torch.all(torch.isfinite(waveform)):
        waveform = torch.nan_to_num(waveform, nan=0.0, posinf=0.0, neginf=0.0)
    return waveform

def normalize_peak_amplitude(waveform: torch.Tensor) -> torch.Tensor:
    """Normalizes maximum absolute amplitude to 1.0."""
    max_val = torch.max(torch.abs(waveform))
    if max_val > 0:
        return waveform / max_val
    return waveform

def pad_or_crop_waveform(
    waveform: torch.Tensor, 
    target_length: int = WINDOW_SAMPLES, 
    mode: str = "deterministic"
) -> torch.Tensor:
    """
    Standardizes waveform length to target_length (64,000 samples = 4.0s).
    - If shorter: right zero-pads to target_length.
    - If longer:
        - "deterministic": slices the first target_length samples (matches inference).
        - "random": selects a random 4-second subsegment (training augmentation).
    """
    length = waveform.shape[-1]

    if length < target_length:
        padding = target_length - length
        return F.pad(waveform, (0, padding))
    elif length > target_length:
        if mode == "random":
            max_start = length - target_length
            start = torch.randint(0, max_start + 1, (1,)).item()
            return waveform[..., start:start + target_length]
        else:
            return waveform[..., :target_length]
    return waveform

def preprocess_audio(
    waveform: torch.Tensor, 
    target_length: int = WINDOW_SAMPLES, 
    mode: str = "deterministic"
) -> torch.Tensor:
    """
    Full preprocessing pipeline:
    Sanitize -> Normalize Peak -> Pad/Crop.
    Produces tensor of shape (1, 64000) ready for LightweightAntiSpoofCNN.
    """
    waveform = sanitize_waveform(waveform)
    waveform = pad_or_crop_waveform(waveform, target_length=target_length, mode=mode)
    waveform = normalize_peak_amplitude(waveform)
    return waveform
