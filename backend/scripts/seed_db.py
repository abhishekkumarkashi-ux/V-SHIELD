import os
import sys

# Add the parent directory to sys.path so we can import app modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import bcrypt
from app.database.database import SessionLocal, engine, Base
from app.database.models import User

def get_password_hash(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def seed_db():
    print("Creating tables if they don't exist...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        email = "admin@vshield.local"
        user = db.query(User).filter(User.email == email).first()
        if user:
            print(f"User {email} already exists.")
        else:
            print(f"Creating user {email}...")
            hashed_password = get_password_hash("admin123")
            new_user = User(
                email=email,
                name="Admin User",
                hashed_password=hashed_password
            )
            db.add(new_user)
            db.commit()
            print("Successfully created admin user.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
