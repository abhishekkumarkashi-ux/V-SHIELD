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

def get_db():
    if SessionLocal:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    else:
        yield None
