"""
Audio processing subpackage for V-SHIELD.
"""

from training.audio.loader import load_audio, TARGET_SAMPLE_RATE
from training.audio.preprocessing import (
    sanitize_waveform, 
    normalize_peak_amplitude, 
    pad_or_crop_waveform, 
    preprocess_audio,
    WINDOW_SAMPLES
)
from training.audio.windowing import extract_sliding_windows, HOP_SAMPLES

__all__ = [
    "load_audio",
    "TARGET_SAMPLE_RATE",
    "sanitize_waveform",
    "normalize_peak_amplitude",
    "pad_or_crop_waveform",
    "preprocess_audio",
    "WINDOW_SAMPLES",
    "extract_sliding_windows",
    "HOP_SAMPLES"
]
