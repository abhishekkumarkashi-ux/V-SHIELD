import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database will be configured in Phase 9
# For Phase 1, we just create the foundation
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./vshield.db")

# Avoid crashing the app if DB is not available in Phase 1
try:
    connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    print(f"Warning: Could not initialize database connection in Phase 1. {e}")
    engine = None
    SessionLocal = None

Base = declarative_base()

def ensure_schema_compatibility(engine):
    """Ensure existing SQLite schema matches SQLAlchemy models without dropping data."""
    if not engine or not str(engine.url).startswith("sqlite"):
        return
    import sqlite3
    db_path = str(engine.url).replace("sqlite:///", "").replace("sqlite://", "")
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(analysis_history)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if existing_cols:
                columns_to_add = [
                    ("call_id", "VARCHAR"),
                    ("caller_ani", "VARCHAR"),
                    ("caller_origin", "VARCHAR"),
                    ("target_desk", "VARCHAR"),
                    ("duration_seconds", "INTEGER")
                ]
                for col_name, col_type in columns_to_add:
                    if col_name not in existing_cols:
                        cursor.execute(f"ALTER TABLE analysis_history ADD COLUMN {col_name} {col_type}")
                conn.commit()
            conn.close()
        except Exception as e:
            print(f"Warning during schema compatibility check: {e}")

def get_db():
    if SessionLocal:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    else:
        yield None
