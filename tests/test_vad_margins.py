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


def test_vad_discrimination_silence_speech_noise():
    """
    Phase 6 Requirement:
    Verifies that VAD strictly distinguishes:
    1. Silence
    2. Normal speech
    3. Loud speech
    4. Ambient background noise
    """
    vad = MarginPreservingVAD(sample_rate=16000, energy_threshold=0.005)
    t = np.linspace(0, 1.0, 16000, endpoint=False, dtype=np.float32)

    # 1. Silence
    silence = np.zeros(16000, dtype=np.float32)
    diag_silence = vad.analyze_speech(silence)
    assert diag_silence["state"] == "SILENCE"
    assert not diag_silence["is_speech_active"]
    assert diag_silence["speech_ratio"] == 0.0

    # 2. Normal speech (RMS ~ 0.14 > 0.005)
    normal_speech = (0.2 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    diag_normal = vad.analyze_speech(normal_speech)
    assert diag_normal["state"] == "SPEECH"
    assert diag_normal["is_speech_active"]
    assert diag_normal["speech_ratio"] > 0.5
    assert diag_normal["mean_frame_rms"] > 0.05

    # 3. Loud speech (RMS ~ 0.56 > 0.005)
    loud_speech = (0.8 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    diag_loud = vad.analyze_speech(loud_speech)
    assert diag_loud["state"] == "SPEECH"
    assert diag_loud["is_speech_active"]
    assert diag_loud["speech_ratio"] > 0.5
    assert diag_loud["mean_frame_rms"] > 0.2

    # 4. Background noise (RMS ~ 0.001 < 0.005 threshold)
    np.random.seed(42)
    bg_noise = np.random.uniform(-0.002, 0.002, 16000).astype(np.float32)
    diag_noise = vad.analyze_speech(bg_noise)
    assert diag_noise["state"] == "SILENCE"
    assert not diag_noise["is_speech_active"]
    assert diag_noise["active_frames_count"] == 0


def test_vad_transient_click_rejection():
    """Verify that transient acoustic clicks (< 50ms) do not trigger false positive speech."""
    vad = MarginPreservingVAD(sample_rate=16000, energy_threshold=0.005, min_speech_duration_ms=50)

    # 1 second of audio with a 15ms (240 samples) loud transient click in the middle
    audio = np.zeros(16000, dtype=np.float32)
    click_start = 8000
    click_end = click_start + 240
    audio[click_start:click_end] = 0.9  # very loud click

    diag = vad.analyze_speech(audio)
    assert diag["state"] == "SILENCE"
    assert not diag["is_speech_active"]
