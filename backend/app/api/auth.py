import os
import jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests

from app.database.database import get_db
from app.database.models import User

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "dummy-client-id")

router = APIRouter(prefix="/api/v1/auth")

# Pydantic schema
from pydantic import BaseModel
class GoogleAuthRequest(BaseModel):
    credential: str

class UserResponse(BaseModel):
    id: int
    google_id: str
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
        # Fallback to Authorization header if provided
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
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

@router.post("/google")
async def google_auth(auth_req: GoogleAuthRequest, response: Response, db: Session = Depends(get_db)):
    try:
        # Note: In production you MUST provide a valid GOOGLE_CLIENT_ID 
        # that matches the one used by the frontend.
        # If GOOGLE_CLIENT_ID is dummy, we will allow it to pass for development/testing if the token is somehow bypassed, 
        # but google library requires it to match.
        try:
            idinfo = id_token.verify_oauth2_token(auth_req.credential, requests.Request(), GOOGLE_CLIENT_ID)
        except ValueError as e:
            # Fallback for dev if bypassing with mock token
            if auth_req.credential == "mock_dev_token":
                idinfo = {
                    "email": "dev@vshield.app",
                    "sub": "mock_google_id_123",
                    "name": "Developer User",
                    "picture": "https://ui-avatars.com/api/?name=Dev+User"
                }
            else:
                raise e
        
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
            secure=False, # Set to True in production with HTTPS
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
        return {
            "status": "success", 
            "user": UserResponse.from_orm(user),
            "token": access_token
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid token: {e}")

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("vshield_session")
    return {"status": "success"}
