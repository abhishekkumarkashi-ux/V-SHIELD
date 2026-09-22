"""
V-SHIELD Unified Database Adapter (SIH 2026).
Supports:
1. SQLite (Default for local development and offline unit tests).
2. PostgreSQL (Production standard for Render managed databases).

Dynamically toggles between PostgreSQL and SQLite based on DATABASE_URL.
Safely falls back to SQLite if PostgreSQL driver is unavailable.
"""

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings

logger = logging.getLogger("vshield.db")


def is_postgres_configured() -> bool:
    """Returns True if DATABASE_URL indicates a PostgreSQL database."""
    db_url = getattr(settings, "DATABASE_URL", None)
    if not db_url or not isinstance(db_url, str):
        return False
    normalized = db_url.strip().lower()
    return normalized.startswith("postgresql://") or normalized.startswith("postgres://")


def _get_postgres_dsn() -> str:
    """Normalizes postgres:// to postgresql:// for standard driver compatibility."""
    db_url = (getattr(settings, "DATABASE_URL", "") or "").strip()
    if db_url.startswith("postgres://"):
        return "postgresql://" + db_url[len("postgres://") :]
    return db_url


def get_active_backend(db_path: Optional[str] = None) -> str:
    """Determines whether to use 'postgresql' or 'sqlite'."""
    # Explicit custom SQLite path (common in unit tests) forces SQLite
    if db_path and not (db_path.startswith("postgresql://") or db_path.startswith("postgres://")):
        return "sqlite"
    if is_postgres_configured():
        try:
            import psycopg2  # noqa: F401

            return "postgresql"
        except ImportError:
            logger.warning(
                "[DB] DATABASE_URL is set for PostgreSQL, but 'psycopg2' is not installed. "
                "Falling back to SQLite."
            )
            return "sqlite"
    return "sqlite"


def init_db(db_path: Optional[str] = None) -> None:
    """Initializes the speakers biometric table and indexes on the active database backend."""
    backend = get_active_backend(db_path)

    if backend == "postgresql":
        import psycopg2

        dsn = _get_postgres_dsn()
        conn = psycopg2.connect(dsn)
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS speakers (
                            speaker_id VARCHAR(255) PRIMARY KEY,
                            name VARCHAR(255),
                            enrolled_at DOUBLE PRECISION,
                            embedding BYTEA
                        );
                        CREATE INDEX IF NOT EXISTS idx_speakers_enrolled_at ON speakers (enrolled_at);
                    """)
            logger.info("[DB] PostgreSQL speakers table and index initialized successfully.")
        finally:
            conn.close()
    else:
        sqlite_file = db_path or str(settings.SPEAKERS_DB_PATH)
        parent_dir = os.path.dirname(os.path.abspath(sqlite_file))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        conn = sqlite3.connect(sqlite_file)
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS speakers (
                        speaker_id TEXT PRIMARY KEY,
                        name TEXT,
                        enrolled_at REAL,
                        embedding BLOB
                    );
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_speakers_enrolled_at ON speakers (enrolled_at);
                """)
        finally:
            conn.close()


def load_speakers_from_db(
    db_path: Optional[str] = None,
) -> List[Tuple[str, str, float, bytes]]:
    """
    Retrieves all enrolled speaker records from the database.
    Returns list of (speaker_id, name, enrolled_at, embedding_bytes).
    """
    backend = get_active_backend(db_path)
    records: List[Tuple[str, str, float, bytes]] = []

    if backend == "postgresql":
        import psycopg2

        dsn = _get_postgres_dsn()
        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT speaker_id, name, enrolled_at, embedding FROM speakers")
                for row in cur.fetchall():
                    speaker_id, name, enrolled_at, emb_val = row
                    emb_bytes = bytes(emb_val) if emb_val is not None else b""
                    records.append((str(speaker_id), str(name or ""), float(enrolled_at or 0.0), emb_bytes))
        finally:
            conn.close()
    else:
        sqlite_file = db_path or str(settings.SPEAKERS_DB_PATH)
        if not os.path.exists(sqlite_file):
            return []
        conn = sqlite3.connect(sqlite_file)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT speaker_id, name, enrolled_at, embedding FROM speakers")
            for row in cursor.fetchall():
                speaker_id, name, enrolled_at, emb_val = row
                emb_bytes = bytes(emb_val) if emb_val is not None else b""
                records.append((str(speaker_id), str(name or ""), float(enrolled_at or 0.0), emb_bytes))
        finally:
            conn.close()

    return records


def save_speaker_to_db(
    speaker_id: str,
    name: str,
    enrolled_at: float,
    embedding_bytes: bytes,
    db_path: Optional[str] = None,
) -> None:
    """Inserts or updates a speaker biometric profile in the database."""
    backend = get_active_backend(db_path)

    if backend == "postgresql":
        import psycopg2

        dsn = _get_postgres_dsn()
        conn = psycopg2.connect(dsn)
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO speakers (speaker_id, name, enrolled_at, embedding)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (speaker_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            enrolled_at = EXCLUDED.enrolled_at,
                            embedding = EXCLUDED.embedding;
                        """,
                        (speaker_id, name, enrolled_at, psycopg2.Binary(embedding_bytes)),
                    )
        finally:
            conn.close()
    else:
        sqlite_file = db_path or str(settings.SPEAKERS_DB_PATH)
        parent_dir = os.path.dirname(os.path.abspath(sqlite_file))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        conn = sqlite3.connect(sqlite_file)
        try:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO speakers (speaker_id, name, enrolled_at, embedding) VALUES (?, ?, ?, ?)",
                    (speaker_id, name, enrolled_at, sqlite3.Binary(embedding_bytes)),
                )
        finally:
            conn.close()


def check_db_health(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Tests connectivity to active database and returns health metadata."""
    backend = get_active_backend(db_path)
    try:
        if backend == "postgresql":
            import psycopg2

            dsn = _get_postgres_dsn()
            conn = psycopg2.connect(dsn)
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM speakers")
                    count = cur.fetchone()[0]
                return {
                    "status": "ok",
                    "backend": "postgresql",
                    "enrolled_speakers_count": int(count),
                }
            finally:
                conn.close()
        else:
            sqlite_file = db_path or str(settings.SPEAKERS_DB_PATH)
            if not os.path.exists(sqlite_file):
                return {"status": "ok", "backend": "sqlite", "enrolled_speakers_count": 0}
            conn = sqlite3.connect(sqlite_file)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM speakers")
                count = cursor.fetchone()[0]
                return {
                    "status": "ok",
                    "backend": "sqlite",
                    "enrolled_speakers_count": int(count),
                }
            finally:
                conn.close()
    except Exception as exc:
        return {
            "status": "degraded",
            "backend": backend,
            "error": str(exc),
        }
