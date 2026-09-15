"""
Audio Loader for V-SHIELD.
Loads audio from disk using soundfile/torchaudio, converts to mono, and resamples to 16kHz.
"""

import torch
import torchaudio
import soundfile as sf
import numpy as np
from typing import Tuple

TARGET_SAMPLE_RATE = 16000

def load_audio(file_path: str, target_sr: int = TARGET_SAMPLE_RATE) -> Tuple[torch.Tensor, int]:
    """
    Loads an audio file, converts to mono float32, and resamples to target_sr if needed.
    Returns tensor of shape (1, num_samples) and sample rate.
    """
    try:
        # soundfile is robust across platforms
        data, sr = sf.read(file_path, dtype="float32")
        waveform = torch.from_numpy(data)

        # Handle channels
        if waveform.dim() == 1:
            # (time,) -> (1, time)
            waveform = waveform.unsqueeze(0)
        elif waveform.dim() == 2:
            # (time, channels) -> (channels, time)
            waveform = waveform.t()
            # Convert multi-channel to mono via mean
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)

    except Exception:
        # Fallback to torchaudio
        waveform, sr = torchaudio.load(file_path)
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

    # Resample if needed
    if sr != target_sr:
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=target_sr)
        waveform = resampler(waveform)
        sr = target_sr

    return waveform, sr
