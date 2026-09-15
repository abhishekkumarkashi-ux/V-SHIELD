"""
Sliding Window Generator for V-SHIELD.
Extracts 4.0-second evaluation windows with 1.0-second hops matching AUDIO_PROTOCOL.
"""

import torch
from typing import List
from training.audio.preprocessing import pad_or_crop_waveform, normalize_peak_amplitude

WINDOW_SAMPLES = 64000  # 4.0s
HOP_SAMPLES = 16000     # 1.0s

def extract_sliding_windows(
    waveform: torch.Tensor, 
    window_samples: int = WINDOW_SAMPLES, 
    hop_samples: int = HOP_SAMPLES
) -> List[torch.Tensor]:
    """
    Slices a continuous waveform into overlapping windows of shape (1, window_samples).
    If waveform is shorter than window_samples, returns a single padded window.
    """
    total_samples = waveform.shape[-1]
    if total_samples <= window_samples:
        window = pad_or_crop_waveform(waveform, target_length=window_samples, mode="deterministic")
        return [normalize_peak_amplitude(window)]

    windows: List[torch.Tensor] = []
    start = 0
    while start + window_samples <= total_samples:
        w = waveform[..., start:start + window_samples]
        windows.append(normalize_peak_amplitude(w))
        start += hop_samples

    # If the tail has remaining speech > 1 second (16000 samples), pad and include
    if total_samples - start >= hop_samples:
        tail = waveform[..., start:]
        padded_tail = pad_or_crop_waveform(tail, target_length=window_samples, mode="deterministic")
        windows.append(normalize_peak_amplitude(padded_tail))

    return windows
