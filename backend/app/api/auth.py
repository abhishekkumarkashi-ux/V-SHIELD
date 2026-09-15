import os
import jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests
import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        return False

from app.database.database import get_db
from app.database.models import User

from dotenv import load_dotenv

load_dotenv()

# Configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
SECRET_KEY = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY")

if ENVIRONMENT == "production" and not SECRET_KEY:
    raise RuntimeError("JWT_SECRET environment variable is mandatory in production")

if not SECRET_KEY:
    SECRET_KEY = "vshield-development-secret-key-32-bytes-long!"

IS_SECURE_COOKIE = (ENVIRONMENT == "production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

router = APIRouter(prefix="/api/v1/auth")

# Pydantic schema
from pydantic import BaseModel
class GoogleAuthRequest(BaseModel):
    credential: str

class LoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    google_id: Optional[str] = None
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None

    class Config:
        from_attributes = True

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user_from_token(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except jwt.PyJWTError:
        return None
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    return user

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("vshield_session")
            
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
        
    user = get_current_user_from_token(token, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    return user

@router.post("/login")
async def login(login_req: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login_req.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not verify_password(login_req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    response.set_cookie(
        key="vshield_session",
        value=access_token,
        httponly=True,
        secure=IS_SECURE_COOKIE,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    return {
        "status": "success", 
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user)
    }

@router.post("/google")
async def google_auth(auth_req: GoogleAuthRequest, response: Response, db: Session = Depends(get_db)):
    try:
        if not GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=400, detail="Google authentication is not configured on the server")
            
        try:
            idinfo = id_token.verify_oauth2_token(auth_req.credential, requests.Request(), GOOGLE_CLIENT_ID)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid Google token: {e}")
        
        email = idinfo.get('email')
        google_id = idinfo.get('sub')
        name = idinfo.get('name')
        picture = idinfo.get('picture')
        
        if not email:
            raise HTTPException(status_code=400, detail="Invalid Google token")
            
        # Check if user exists
        user = db.query(User).filter(User.email == email).first()
        if not user:
            # Create user
            user = User(
                email=email,
                google_id=google_id,
                name=name,
                picture=picture
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            # Update user info if needed
            if user.google_id != google_id:
                user.google_id = google_id
            if name:
                user.name = name
            if picture:
                user.picture = picture
            db.commit()
            
        # Create token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )
        
        # Set HTTP-only cookie (for future-proofing / same-origin)
        response.set_cookie(
            key="vshield_session",
            value=access_token,
            httponly=True,
            secure=IS_SECURE_COOKIE,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
        return {
            "status": "success", 
            "user": UserResponse.from_orm(user)
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Authentication error: {e}")

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key="vshield_session",
        httponly=True,
        secure=IS_SECURE_COOKIE,
        samesite="lax"
    )
    return {"status": "success"}
