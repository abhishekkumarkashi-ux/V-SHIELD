"""
Unit & Integration tests for POST /api/v1/analyze-file (SIH 2026).
Verifies:
1. Multipart file upload and JSON response schema.
2. ASVspoof repeat-padding (short audio) and truncation (long audio).
3. 8 kHz telephony resampling to 16 kHz mono.
4. Risk classification states (HIGH_RISK_CLONE, BONA_FIDE_GENUINE, WRONG_SPEAKER).
"""

import io
import wave

import numpy as np
import torch
from app.core.audio_processor import (
    load_audio_from_bytes,
    pad_or_truncate_asvspoof,
    resample_to_mono_16k,
)
from app.core.risk_engine import RiskEngine
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def create_mock_wav(
    duration_sec: float = 1.0, sample_rate: int = 16000, frequency: float = 440.0
) -> bytes:
    """Helper to generate in-memory synthetic PCM16 WAV bytes."""
    n_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, n_samples, endpoint=False)
    samples = (0.5 * np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


def test_asvspoof_repeat_padding_short_audio():
    """Short audio (<64,600 samples) must be repeat-padded (looped) until exactly 64,600."""
    short_len = 16000  # 1.0 second
    wav = torch.randn(1, short_len)
    padded = pad_or_truncate_asvspoof(wav, target_samples=64600)

    assert padded.shape == (1, 64600)
    # The first 16,000 samples should match the second 16,000 samples (looping)
    assert torch.allclose(padded[:, :short_len], padded[:, short_len : 2 * short_len])


def test_asvspoof_truncation_long_audio():
    """Long audio (>64,600 samples) must be truncated to exactly 64,600."""
    long_len = 80000  # 5.0 seconds
    wav = torch.randn(1, long_len)
    truncated = pad_or_truncate_asvspoof(wav, target_samples=64600)

    assert truncated.shape == (1, 64600)
    assert torch.allclose(truncated, wav[:, :64600])


def test_narrowband_8k_resampling():
    """8 kHz telephony audio must be upsampled to 16 kHz mono."""
    wav_8k_bytes = create_mock_wav(duration_sec=1.0, sample_rate=8000, frequency=300.0)
    raw_wav, sr = load_audio_from_bytes(wav_8k_bytes)
    assert sr == 8000

    wav_16k = resample_to_mono_16k(raw_wav, sr=sr, target_sr=16000)
    assert wav_16k.shape == (1, 16000)


def test_analyze_file_endpoint_schema():
    """Tests POST /api/v1/analyze-file with valid multipart audio uploads."""
    ref_wav = create_mock_wav(duration_sec=2.0, sample_rate=16000, frequency=440.0)
    test_wav = create_mock_wav(duration_sec=2.5, sample_rate=16000, frequency=440.0)

    response = client.post(
        "/api/v1/analyze-file",
        files={
            "reference_audio": ("ref.wav", ref_wav, "audio/wav"),
            "test_audio": ("test.wav", test_wav, "audio/wav"),
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify JSON schema contracts
    assert data["status"] == "success"
    assert "risk_score" in data
    assert 0.0 <= data["risk_score"] <= 100.0
    assert "classification" in data
    assert "telemetry" in data
    assert "spoof_probability" in data["telemetry"]
    assert "speaker_similarity" in data["telemetry"]
    assert "message" in data


def test_risk_classification_decision_logic():
    """Verifies the four primary static file risk classifications."""
    engine = RiskEngine()

    # 1. High Spoof (>0.65) + High Sim (>0.70) => HIGH_RISK_CLONE
    score1, class1, msg1 = engine.classify_static_file(spoof_prob=0.92, speaker_similarity=0.85)
    assert class1 == "HIGH_RISK_CLONE"
    assert score1 >= 75.0
    assert "MFA recommended" in msg1

    # 2. Low Spoof (<0.30) + High Sim (>0.70) => BONA_FIDE_GENUINE
    score2, class2, msg2 = engine.classify_static_file(spoof_prob=0.10, speaker_similarity=0.88)
    assert class2 == "BONA_FIDE_GENUINE"
    assert score2 <= 30.0
    assert "Genuine caller" in msg2

    # 3. Low Spoof (<0.30) + Low Sim (<0.40) => WRONG_SPEAKER
    score3, class3, msg3 = engine.classify_static_file(spoof_prob=0.15, speaker_similarity=0.25)
    assert class3 == "WRONG_SPEAKER"
    assert 50.0 <= score3 <= 65.0
    assert "mismatch" in msg3

    # 4. High Spoof (>0.65) + Low Sim (<=0.70) => SYNTHETIC_IMPERSONATION
    score4, class4, msg4 = engine.classify_static_file(spoof_prob=0.88, speaker_similarity=0.30)
    assert class4 == "SYNTHETIC_IMPERSONATION"
    assert score4 >= 80.0
    assert "Synthetic" in msg4
