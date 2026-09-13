import pytest
from app.api.auth import create_access_token, get_current_user_from_token
from app.database.database import SessionLocal, engine, Base
from app.database.models import User
from datetime import timedelta
import os

os.environ["JWT_SECRET"] = "test_secret"

@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

def test_create_and_verify_token(db):
    # Ensure clean state
    db.query(User).filter(User.email == "test@test.com").delete()
    db.commit()
    
    user = User(email="test@test.com", google_id="123")
    db.add(user)
    db.commit()
    db.refresh(user)
    
    token = create_access_token({"sub": str(user.id)}, timedelta(minutes=15))
    assert token is not None
    
    decoded_user = get_current_user_from_token(token, db)
    assert decoded_user.id == user.id
    assert decoded_user.email == "test@test.com"

def test_invalid_token(db):
    decoded_user = get_current_user_from_token("invalid.token.here", db)
    assert decoded_user is None
