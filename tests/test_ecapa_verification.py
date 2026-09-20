"""
Unit and Integration Tests for ECAPA-TDNN Speaker Biometric Verification (SIH 2026).
Validates 192-d embedding extraction, Float32/PCM16 audio input handling,
SQLite persistence, and explicit biometric verification states (NO_VOICEPRINT, VERIFIED, MISMATCH, EVALUATING).
"""

import sqlite3

import numpy as np
import pytest
import torch
from app.models.ecapa_service import ECAPAService


@pytest.fixture
def temp_ecapa_svc(tmp_path):
    """Provides an isolated ECAPAService instance backed by a temporary SQLite database."""
    db_file = str(tmp_path / "test_speakers.db")
    svc = ECAPAService(db_path=db_file)
    return svc


def test_extract_embedding_192_dimensional(temp_ecapa_svc):
    """Verifies that extracted embeddings are exactly 192-dimensional with unit L2 norm."""
    np.random.seed(42)
    # 1 second of 16 kHz audio
    audio_f32 = np.random.uniform(-0.5, 0.5, size=16000).astype(np.float32)

    emb = temp_ecapa_svc.extract_embedding(audio_f32)
    assert isinstance(emb, np.ndarray)
    assert emb.shape == (192,)
    assert emb.dtype == np.float32

    # L2 norm should be normalized to ~1.0
    norm = np.linalg.norm(emb)
    assert np.isclose(norm, 1.0, atol=1e-3)


def test_extract_embedding_input_audio_formats(temp_ecapa_svc):
    """
    Verifies that extract_embedding supports:
    1. Float32 bytes (raw Web Audio stream)
    2. PCM16 bytes
    3. 1D/2D numpy.ndarray
    4. torch.Tensor
    """
    np.random.seed(123)
    raw_samples = np.random.uniform(-0.4, 0.4, size=16000).astype(np.float32)

    # 1. Float32 bytes
    f32_bytes = raw_samples.tobytes()
    emb_f32_bytes = temp_ecapa_svc.extract_embedding(f32_bytes)
    assert emb_f32_bytes.shape == (192,)

    # 2. PCM16 bytes
    pcm16_samples = (raw_samples * 32767).astype(np.int16)
    pcm16_bytes = pcm16_samples.tobytes()
    emb_pcm16_bytes = temp_ecapa_svc.extract_embedding(pcm16_bytes)
    assert emb_pcm16_bytes.shape == (192,)

    # 3. 2D numpy array
    arr_2d = raw_samples.reshape(1, -1)
    emb_2d = temp_ecapa_svc.extract_embedding(arr_2d)
    assert emb_2d.shape == (192,)

    # 4. torch.Tensor
    tensor_input = torch.from_numpy(raw_samples)
    emb_tensor = temp_ecapa_svc.extract_embedding(tensor_input)
    assert emb_tensor.shape == (192,)


def test_speaker_enrollment_and_sqlite_persistence(tmp_path):
    """
    Verifies speaker enrollment, SQLite schema/table insertion,
    and cache reloading across separate service instances.
    """
    db_file = str(tmp_path / "persistence_test.db")
    svc_1 = ECAPAService(db_path=db_file)

    np.random.seed(99)
    enroll_audio = np.random.uniform(-0.3, 0.3, size=16000).astype(np.float32)

    emb_1 = svc_1.enroll_speaker(
        speaker_id="exec-test-42",
        audio=enroll_audio,
        name="Dr. Jane Doe",
    )

    assert emb_1.shape == (192,)
    assert "exec-test-42" in svc_1._enrolled_embeddings

    # Check directly inside SQLite database
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT speaker_id, name, embedding FROM speakers WHERE speaker_id=?", ("exec-test-42",))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "exec-test-42"
        assert row[1] == "Dr. Jane Doe"
        saved_emb = np.frombuffer(row[2], dtype=np.float32)
        assert saved_emb.shape == (192,)
        assert np.allclose(saved_emb, emb_1, atol=1e-5)

    # Instantiate a second service from the same DB file and verify persistence
    svc_2 = ECAPAService(db_path=db_file)
    assert "exec-test-42" in svc_2._enrolled_embeddings
    reloaded_emb = svc_2.get_speaker_embedding("exec-test-42")
    assert reloaded_emb is not None
    assert np.allclose(reloaded_emb, emb_1, atol=1e-5)


def test_verify_speaker_detailed_no_voiceprint(temp_ecapa_svc):
    """
    Verifies that querying an unknown speaker or None returns status='NO_VOICEPRINT'
    with similarity=None, has_voiceprint=False, and is_match=False.
    """
    audio = np.random.uniform(-0.2, 0.2, size=16000).astype(np.float32)

    # 1. Unenrolled speaker ID
    res_unknown = temp_ecapa_svc.verify_speaker_detailed(audio, speaker_id="nonexistent-user")
    assert res_unknown["status"] == "NO_VOICEPRINT"
    assert res_unknown["similarity"] is None
    assert res_unknown["has_voiceprint"] is False
    assert res_unknown["is_match"] is False
    assert res_unknown["speaker_id"] == "nonexistent-user"

    # 2. None speaker ID
    res_none = temp_ecapa_svc.verify_speaker_detailed(audio, speaker_id=None)
    assert res_none["status"] == "NO_VOICEPRINT"
    assert res_none["similarity"] is None
    assert res_none["has_voiceprint"] is False
    assert res_none["is_match"] is False

    # 3. Empty string speaker ID
    res_empty = temp_ecapa_svc.verify_speaker_detailed(audio, speaker_id="")
    assert res_empty["status"] == "NO_VOICEPRINT"
    assert res_empty["similarity"] is None
    assert res_empty["has_voiceprint"] is False
    assert res_empty["is_match"] is False


def test_verify_speaker_detailed_verified_match(temp_ecapa_svc):
    """
    Verifies that matching audio (similarity >= 0.70) yields status='VERIFIED'
    and is_match=True.
    """
    np.random.seed(77)
    audio = np.random.uniform(-0.3, 0.3, size=16000).astype(np.float32)

    temp_ecapa_svc.enroll_speaker("speaker-alpha", audio, name="Alpha User")

    # Verify using the identical audio sample
    result = temp_ecapa_svc.verify_speaker_detailed(audio, speaker_id="speaker-alpha")
    assert result["status"] == "VERIFIED"
    assert result["is_match"] is True
    assert result["has_voiceprint"] is True
    assert result["similarity"] is not None
    assert result["similarity"] >= 0.70


def test_verify_speaker_detailed_mismatch_and_evaluating(temp_ecapa_svc):
    """
    Verifies threshold behavior:
    similarity <= 0.40 -> 'MISMATCH'
    0.40 < similarity < 0.70 -> 'EVALUATING'
    """
    # Force mock embeddings to test exact threshold boundary conditions
    emb_target = np.zeros(192, dtype=np.float32)
    emb_target[0] = 1.0  # Unit vector along axis 0

    temp_ecapa_svc._enrolled_embeddings["target-speaker"] = emb_target
    temp_ecapa_svc._enrolled_metadata["target-speaker"] = {
        "speaker_id": "target-speaker",
        "name": "Target",
        "enrolled_at": 1000.0,
    }

    # Helper to mock extract_embedding for testing boundary branches
    original_extract = temp_ecapa_svc.extract_embedding

    try:
        # Case 1: Cosine similarity 0.25 <= 0.40 -> MISMATCH
        emb_mismatch = np.zeros(192, dtype=np.float32)
        emb_mismatch[0] = 0.25
        emb_mismatch[1] = np.sqrt(1.0 - 0.25**2)
        temp_ecapa_svc.extract_embedding = lambda audio: emb_mismatch

        res_mismatch = temp_ecapa_svc.verify_speaker_detailed(b"dummy", "target-speaker")
        assert res_mismatch["status"] == "MISMATCH"
        assert res_mismatch["is_match"] is False
        assert res_mismatch["has_voiceprint"] is True
        assert np.isclose(res_mismatch["similarity"], 0.25, atol=1e-3)

        # Case 2: Cosine similarity 0.55 (between 0.40 and 0.70) -> EVALUATING
        emb_eval = np.zeros(192, dtype=np.float32)
        emb_eval[0] = 0.55
        emb_eval[1] = np.sqrt(1.0 - 0.55**2)
        temp_ecapa_svc.extract_embedding = lambda audio: emb_eval

        res_eval = temp_ecapa_svc.verify_speaker_detailed(b"dummy", "target-speaker")
        assert res_eval["status"] == "EVALUATING"
        assert res_eval["is_match"] is False
        assert res_eval["has_voiceprint"] is True
        assert np.isclose(res_eval["similarity"], 0.55, atol=1e-3)

        # Case 3: Cosine similarity 0.85 >= 0.70 -> VERIFIED
        emb_verified = np.zeros(192, dtype=np.float32)
        emb_verified[0] = 0.85
        emb_verified[1] = np.sqrt(1.0 - 0.85**2)
        temp_ecapa_svc.extract_embedding = lambda audio: emb_verified

        res_verified = temp_ecapa_svc.verify_speaker_detailed(b"dummy", "target-speaker")
        assert res_verified["status"] == "VERIFIED"
        assert res_verified["is_match"] is True
        assert res_verified["has_voiceprint"] is True
        assert np.isclose(res_verified["similarity"], 0.85, atol=1e-3)

    finally:
        temp_ecapa_svc.extract_embedding = original_extract
