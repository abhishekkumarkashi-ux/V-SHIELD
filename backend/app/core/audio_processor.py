"""
Static Audio File Preprocessor for V-SHIELD (SIH 2026).
Implements official ASVspoof 2019/2021 repeat-padding / truncation standards,
16 kHz mono resampling, and 300 ms VAD margin preservation.
"""

import io
import math
from typing import Tuple

import numpy as np
import soundfile as sf
import torch
import torchaudio
from scipy import signal

from app.core.vad import MarginPreservingVAD


def load_audio_from_bytes(file_bytes: bytes) -> Tuple[torch.Tensor, int]:
    """
    Decodes audio bytes (WAV, FLAC, OGG, PCM) into a PyTorch Float32 tensor and sample rate.
    Tries torchaudio first, falling back to soundfile if TorchCodec is unavailable.
    """
    if not file_bytes:
        raise ValueError("Empty audio payload received.")

    # 1. Try torchaudio native load
    try:
        buf = io.BytesIO(file_bytes)
        wav, sr = torchaudio.load(buf)
        return wav.to(torch.float32), sr
    except Exception:
        pass

    # 2. Try soundfile
    try:
        buf = io.BytesIO(file_bytes)
        data, sr = sf.read(buf, dtype="float32")
        wav = torch.from_numpy(data)
        if wav.ndim == 1:
            wav = wav.unsqueeze(0)
        elif wav.ndim == 2 and wav.shape[1] < wav.shape[0]:
            # Convert (samples, channels) -> (channels, samples)
            wav = wav.transpose(0, 1)
        return wav, sr
    except Exception:
        pass

    # 3. Fallback: Raw 16-bit PCM (assuming 16 kHz mono if headerless)
    try:
        valid_len = (len(file_bytes) // 2) * 2
        int16_data = np.frombuffer(file_bytes[:valid_len], dtype=np.int16)
        float_data = int16_data.astype(np.float32) / 32768.0
        wav = torch.from_numpy(float_data).unsqueeze(0)
        return wav, 16000
    except Exception as e:
        raise ValueError(f"Failed to decode audio bytes: {e}")


def resample_to_mono_16k(wav: torch.Tensor, sr: int, target_sr: int = 16000) -> torch.Tensor:
    """
    Converts multi-channel audio to mono and resamples to target_sr (16,000 Hz).
    """
    # 1. Convert to mono (1, N)
    if wav.ndim == 1:
        wav = wav.unsqueeze(0)
    elif wav.shape[0] > 1:
        wav = torch.mean(wav, dim=0, keepdim=True)

    # 2. Resample if necessary
    if sr != target_sr:
        try:
            resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=target_sr)
            wav = resampler(wav)
        except Exception:
            # Fallback to scipy polyphase resampling
            common = math.gcd(sr, target_sr)
            up = target_sr // common
            down = sr // common
            arr = wav.squeeze(0).numpy()
            resampled_arr = signal.resample_poly(arr, up=up, down=down).astype(np.float32)
            wav = torch.from_numpy(resampled_arr).unsqueeze(0)

    return wav.to(torch.float32)


def pad_or_truncate_asvspoof(wav: torch.Tensor, target_samples: int = 64600) -> torch.Tensor:
    """
    Official ASVspoof standard padding / truncating for AASIST:
    - If length > 64,600: Truncate to first 64,600 samples.
    - If length < 64,600: Repeat-pad (loop) until exactly 64,600 samples.
    """
    if wav.ndim == 1:
        wav = wav.unsqueeze(0)

    cur_len = wav.shape[-1]
    if cur_len == 0:
        return torch.zeros((1, target_samples), dtype=torch.float32)

    if cur_len > target_samples:
        return wav[:, :target_samples]
    elif cur_len < target_samples:
        repeats = int(math.ceil(target_samples / cur_len))
        repeated = wav.repeat(1, repeats)
        return repeated[:, :target_samples]

    return wav


def preprocess_static_audio(
    file_bytes: bytes, target_sr: int = 16000, target_samples: int = 64600, apply_vad: bool = True
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Complete static audio preprocessing pipeline:
    1. Loads bytes & resamples to 16 kHz mono.
    2. Applies VAD margin-preservation (preserving 300ms margins).
    3. Repeat-pads or truncates to exactly 64,600 samples according to ASVspoof rules.

    Returns:
        full_waveform (torch.Tensor): Uncut 16 kHz mono waveform (for ECAPA-TDNN).
        padded_waveform (torch.Tensor): Shaped (1, 64600) for AASIST.
    """
    raw_wav, sr = load_audio_from_bytes(file_bytes)
    wav_16k = resample_to_mono_16k(raw_wav, sr=sr, target_sr=target_sr)

    # VAD Margin Preservation check: Ensure 300 ms ambient margins are retained
    if apply_vad:
        vad = MarginPreservingVAD(sample_rate=target_sr, min_silence_padding_sec=0.30)
        _, _, safe_wav = vad.process_window(wav_16k)
    else:
        safe_wav = wav_16k

    padded_wav = pad_or_truncate_asvspoof(safe_wav, target_samples=target_samples)

    return wav_16k, padded_wav
