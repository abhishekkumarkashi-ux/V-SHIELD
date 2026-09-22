# V-SHIELD Database Architecture & PostgreSQL Migration Guide

**Target Audience**: DevOps Engineers, Security Operators, and Deployment Team  
**Problem Statement ID**: SIH 2026 #26104  
**Scope**: SQLite (Local Development) to PostgreSQL (Render Managed Production)

---

## 1. Overview & Strategy

V-SHIELD employs a dual-database architecture:
- **Local Development / Offline Tests**: Zero-dependency embedded **SQLite** database (`backend/app/vshield.db`), enabling fast offline testing, zero external service dependency, and clean ephemeral test fixtures.
- **Production (Render)**: Managed **PostgreSQL** database service, providing persistent storage for enrolled biometric voiceprints across container deploys, automated backups, and multi-worker concurrency.

The application dynamically detects `DATABASE_URL`:
- If `DATABASE_URL` begins with `postgresql://` or `postgres://`, V-SHIELD connects to PostgreSQL via `psycopg2`.
- If `DATABASE_URL` is omitted, blank, or starts with `sqlite:///`, V-SHIELD falls back to SQLite transparently.

---

## 2. Table Schema & Data Mapping

V-SHIELD maintains a biometric voiceprint registry in the `speakers` table:

### PostgreSQL Production Schema
```sql
CREATE TABLE IF NOT EXISTS speakers (
    speaker_id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255),
    enrolled_at DOUBLE PRECISION,
    embedding BYTEA
);

CREATE INDEX IF NOT EXISTS idx_speakers_enrolled_at ON speakers (enrolled_at);
```

### SQLite Development Schema
```sql
CREATE TABLE IF NOT EXISTS speakers (
    speaker_id TEXT PRIMARY KEY,
    name TEXT,
    enrolled_at REAL,
    embedding BLOB
);

CREATE INDEX IF NOT EXISTS idx_speakers_enrolled_at ON speakers (enrolled_at);
```

### Type Mapping Table
| Column | Purpose | SQLite Type | PostgreSQL Type | Python Type |
| :--- | :--- | :--- | :--- | :--- |
| `speaker_id` | Unique biometric profile ID (e.g. `spk_operator_001`) | `TEXT` | `VARCHAR(255)` | `str` |
| `name` | Human-readable caller / operator name | `TEXT` | `VARCHAR(255)` | `str` |
| `enrolled_at` | Unix epoch enrollment timestamp | `REAL` | `DOUBLE PRECISION` | `float` |
| `embedding` | 192-dimensional ECAPA-TDNN Float32 vector (768 bytes) | `BLOB` | `BYTEA` | `bytes` (`np.ndarray.tobytes()`) |

---

## 3. Production Connection String Format

Render generates standard connection strings for managed PostgreSQL instances:

```text
DATABASE_URL=postgresql://vshield_user:<PASSWORD>@dpg-<INSTANCE_ID>-a.<REGION>-postgres.render.com/vshield
```

> [!NOTE]
> If Render outputs an older `postgres://` prefix instead of `postgresql://`, V-SHIELD automatically normalizes it to `postgresql://` at runtime.

---

## 4. Query & Transaction Semantics

V-SHIELD utilizes database operations with automatic upsert:

- **Initialization**: Executed automatically on application startup via `init_db()`.
- **Query (Cache Population)**:
  ```sql
  SELECT speaker_id, name, enrolled_at, embedding FROM speakers;
  ```
- **Upsert (Biometric Enrollment)**:
  - *PostgreSQL*:
    ```sql
    INSERT INTO speakers (speaker_id, name, enrolled_at, embedding)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (speaker_id) DO UPDATE SET
        name = EXCLUDED.name,
        enrolled_at = EXCLUDED.enrolled_at,
        embedding = EXCLUDED.embedding;
    ```
  - *SQLite*:
    ```sql
    INSERT OR REPLACE INTO speakers (speaker_id, name, enrolled_at, embedding)
    VALUES (?, ?, ?, ?);
    ```

---

## 5. Step-by-Step Production Migration

To migrate existing local enrolled speaker voiceprints from SQLite to your Render PostgreSQL database:

### Prerequisites
Ensure `psycopg2-binary` is installed:
```bash
pip install psycopg2-binary
```

### Run the Migration Utility
```bash
python scripts/migrate_sqlite_to_postgres.py \
  --sqlite backend/app/vshield.db \
  --postgres "postgresql://vshield_user:<PASSWORD>@<HOST>/vshield"
```

### Verify Migration
Run the health check endpoint:
```bash
curl -s https://<RENDER_BACKEND_URL>/health | jq .
```
Expected response:
```json
{
  "status": "ok",
  "model_loaded": true,
  "speaker_verification_loaded": true,
  "enrolled_speakers_count": 3
}
```
