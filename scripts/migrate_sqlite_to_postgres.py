#!/usr/bin/env python3
"""
V-SHIELD SQLite to PostgreSQL Database Migration Utility (SIH 2026).
Usage:
    python scripts/migrate_sqlite_to_postgres.py --sqlite backend/app/vshield.db --postgres "postgresql://user:pass@host:5432/vshield"

Migrates:
- All enrolled biometric voiceprints (speakers table).
- Preserves speaker_id, name, enrolled_at timestamp, and 192-dim Float32 embeddings.
"""

import argparse
import os
import sqlite3
import sys

try:
    import psycopg2
except ImportError:
    print("[ERROR] 'psycopg2' is required for migration to PostgreSQL. Run: pip install psycopg2-binary")
    sys.exit(1)


def migrate(sqlite_path: str, postgres_url: str) -> None:
    if not os.path.exists(sqlite_path):
        print(f"[ERROR] SQLite database file not found at: {sqlite_path}")
        sys.exit(1)

    # Normalize connection string
    dsn = postgres_url.strip()
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://") :]

    print(f"[INFO] Connecting to SQLite: {sqlite_path}")
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_cur = sqlite_conn.cursor()

    try:
        sqlite_cur.execute("SELECT speaker_id, name, enrolled_at, embedding FROM speakers")
        rows = sqlite_cur.fetchall()
        print(f"[INFO] Read {len(rows)} speaker profile(s) from SQLite.")
    except Exception as exc:
        print(f"[ERROR] Failed to query SQLite speakers: {exc}")
        sqlite_conn.close()
        sys.exit(1)

    print(f"[INFO] Connecting to PostgreSQL...")
    try:
        pg_conn = psycopg2.connect(dsn)
    except Exception as exc:
        print(f"[ERROR] Failed to connect to PostgreSQL: {exc}")
        sqlite_conn.close()
        sys.exit(1)

    try:
        with pg_conn:
            with pg_conn.cursor() as pg_cur:
                # 1. Initialize schema
                pg_cur.execute("""
                    CREATE TABLE IF NOT EXISTS speakers (
                        speaker_id VARCHAR(255) PRIMARY KEY,
                        name VARCHAR(255),
                        enrolled_at DOUBLE PRECISION,
                        embedding BYTEA
                    );
                    CREATE INDEX IF NOT EXISTS idx_speakers_enrolled_at ON speakers (enrolled_at);
                """)

                # 2. Insert records
                migrated = 0
                for row in rows:
                    speaker_id, name, enrolled_at, embedding = row
                    pg_cur.execute(
                        """
                        INSERT INTO speakers (speaker_id, name, enrolled_at, embedding)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (speaker_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            enrolled_at = EXCLUDED.enrolled_at,
                            embedding = EXCLUDED.embedding;
                        """,
                        (speaker_id, name, enrolled_at, psycopg2.Binary(embedding)),
                    )
                    migrated += 1

                print(f"[SUCCESS] Successfully migrated {migrated} speaker profile(s) to PostgreSQL!")

    finally:
        sqlite_conn.close()
        pg_conn.close()


def main():
    parser = argparse.ArgumentParser(description="V-SHIELD SQLite to PostgreSQL Database Migrator")
    parser.add_argument(
        "--sqlite",
        default="backend/app/vshield.db",
        help="Path to SQLite database file (default: backend/app/vshield.db)",
    )
    parser.add_argument(
        "--postgres",
        default=os.environ.get("DATABASE_URL", ""),
        help="PostgreSQL connection string (or set DATABASE_URL env var)",
    )

    args = parser.parse_args()
    if not args.postgres:
        print("[ERROR] Please provide --postgres or set the DATABASE_URL environment variable.")
        sys.exit(1)

    migrate(args.sqlite, args.postgres)


if __name__ == "__main__":
    main()
