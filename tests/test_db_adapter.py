"""
Unit tests for V-SHIELD Unified Database Adapter (SIH 2026).
Verifies:
1. SQLite initialization, speaker enrollment, and loading.
2. PostgreSQL detection and fallback behavior.
3. Database health checking.
"""

import os
import tempfile
import numpy as np
import pytest
from app.config import settings
from app.core.db import (
    check_db_health,
    get_active_backend,
    init_db,
    is_postgres_configured,
    load_speakers_from_db,
    save_speaker_to_db,
)


def test_sqlite_db_lifecycle():
    """Verify table initialization, saving and loading speaker voiceprints in SQLite."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        init_db(tmp_path)

        # Health check on fresh DB
        health = check_db_health(tmp_path)
        assert health["status"] == "ok"
        assert health["backend"] == "sqlite"
        assert health["enrolled_speakers_count"] == 0

        # Save speaker
        dummy_embedding = np.random.randn(192).astype(np.float32)
        save_speaker_to_db(
            speaker_id="spk_unit_test_01",
            name="Test Caller",
            enrolled_at=1700000000.0,
            embedding_bytes=dummy_embedding.tobytes(),
            db_path=tmp_path,
        )

        # Load speaker
        records = load_speakers_from_db(tmp_path)
        assert len(records) == 1
        spk_id, name, enrolled_at, emb_bytes = records[0]
        assert spk_id == "spk_unit_test_01"
        assert name == "Test Caller"
        assert enrolled_at == 1700000000.0
        loaded_emb = np.frombuffer(emb_bytes, dtype=np.float32)
        np.testing.assert_allclose(loaded_emb, dummy_embedding, rtol=1e-5)

        # Health check reflects enrolled count
        health_after = check_db_health(tmp_path)
        assert health_after["enrolled_speakers_count"] == 1

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_postgres_detection_and_backend_resolution(monkeypatch):
    """Verify PostgreSQL detection logic based on DATABASE_URL."""
    # When DATABASE_URL is unset
    monkeypatch.setattr(settings, "DATABASE_URL", None)
    assert is_postgres_configured() is False
    assert get_active_backend() == "sqlite"

    # When DATABASE_URL is postgresql
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://user:pass@host:5432/vshield")
    assert is_postgres_configured() is True

    # When DATABASE_URL is postgres (Render shorthand)
    monkeypatch.setattr(settings, "DATABASE_URL", "postgres://user:pass@host:5432/vshield")
    assert is_postgres_configured() is True
