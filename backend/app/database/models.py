from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base
from datetime import datetime
import uuid

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    google_id = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    speaker_profile = relationship("SpeakerProfile", back_populates="user", uselist=False)
    history = relationship("AnalysisHistory", back_populates="user")

class SpeakerProfile(Base):
    __tablename__ = "speaker_profiles"
    
    id = Column(String, primary_key=True, index=True) # UUID string
    user_id = Column(Integer, ForeignKey("users.id"))
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="speaker_profile")

class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # New metadata fields
    call_id = Column(String, index=True, default=lambda: f"#VSH-{uuid.uuid4().hex[:4].upper()}")
    caller_ani = Column(String, nullable=True)
    caller_origin = Column(String, nullable=True)
    target_desk = Column(String, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    risk_score = Column(Float)
    risk_level = Column(String)
    spoof_probability = Column(Float)
    speaker_similarity = Column(Float, nullable=True)
    speaker_status = Column(String)
    
    user = relationship("User", back_populates="history")
    alert = relationship("SecurityAlert", back_populates="analysis", uselist=False)

class SecurityAlert(Base):
    __tablename__ = "security_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String, index=True, unique=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    analysis_id = Column(Integer, ForeignKey("analysis_history.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    severity = Column(String) # CRITICAL, HIGH, MEDIUM, LOW
    title = Column(String)
    caller = Column(String, nullable=True)
    target = Column(String, nullable=True)
    claimed_identity = Column(String, nullable=True)
    risk_score = Column(Integer)
    is_resolved = Column(Boolean, default=False)
    assignee = Column(String, nullable=True)
    
    user = relationship("User")
    analysis = relationship("AnalysisHistory", back_populates="alert")
