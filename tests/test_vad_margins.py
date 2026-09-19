"""
Unit tests for MarginPreservingVAD (SIH 2026).
Ensures minimum 300 ms silence margin preservation (Silence Shortcut Mitigation - ASVspoof 2021).
"""

import numpy as np

try:
    import pytest
except ImportError:
    pytest = None

from app.core.vad import MarginPreservingVAD


def test_vad_margin_preservation_on_isolated_speech():
    sample_rate = 16000
    vad = MarginPreservingVAD(
        sample_rate=sample_rate,
        energy_threshold=0.01,
        min_silence_padding_sec=0.30,  # 300 ms = 4,800 samples
    )

    # 4 seconds total: 1.5s silence + 1.0s speech + 1.5s silence
    total_samples = 64000
    audio = np.zeros(total_samples, dtype=np.float32)

    speech_start = int(1.5 * sample_rate)  # sample 24,000
    speech_end = int(2.5 * sample_rate)  # sample 40,000

    # Inject sinusoidal speech tone (RMS energy ~ 0.35 > 0.01 threshold)
    t = np.linspace(0, 1.0, speech_end - speech_start, endpoint=False)
    audio[speech_start:speech_end] = 0.5 * np.sin(2 * np.pi * 440 * t)

    mask = vad.detect_speech_mask(audio)
    speech_indices = np.where(mask)[0]

    assert len(speech_indices) > 0

    first_mask_idx = speech_indices[0]
    last_mask_idx = speech_indices[-1]

    # Expected margin expansion: 4800 samples before and after
    expected_margin = int(0.30 * sample_rate)

    # The mask must start at least 4800 samples before the actual speech
    leading_margin_preserved = speech_start - first_mask_idx
    trailing_margin_preserved = last_mask_idx - speech_end

    assert (
        leading_margin_preserved >= expected_margin - 400
    )  # Allow frame-boundary tolerance (25ms = 400 samples)
    assert trailing_margin_preserved >= expected_margin - 400


def test_vad_pure_silence():
    vad = MarginPreservingVAD(sample_rate=16000, energy_threshold=0.01)
    silence = np.zeros(64600, dtype=np.float32)

    is_active, ratio, safe_tensor = vad.process_window(silence)
    assert not is_active
    assert ratio == 0.0
    assert safe_tensor.shape[-1] == 64600  # Tensor size preserved without truncation


def test_vad_continuous_speech():
    vad = MarginPreservingVAD(sample_rate=16000, energy_threshold=0.01)
    noise = np.random.uniform(-0.2, 0.2, 64600).astype(np.float32)

    is_active, ratio, _ = vad.process_window(noise)
    assert is_active
    assert ratio > 0.90
