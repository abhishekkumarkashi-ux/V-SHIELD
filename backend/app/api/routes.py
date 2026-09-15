from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from sqlalchemy.orm import Session
from app.ml.inference import get_model_status, run_inference
from app.ml.speaker_verification import speaker_verification_instance
from app.api.speaker_store import save_speaker_embedding
from app.api.auth import get_current_user
from app.database.database import get_db
from app.database.models import User, SpeakerProfile, AnalysisHistory
import uuid
import numpy as np
import io
import soundfile as sf

router = APIRouter(prefix="/api/v1")

@router.get("/status")
async def get_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(SpeakerProfile).filter(SpeakerProfile.user_id == current_user.id).first()
    return {
        "system": "online",
        "ml_model": get_model_status(),
        "speaker_enrolled": profile is not None,
        "speaker_id": profile.id if profile else None
    }

@router.get("/history")
async def get_history(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    history = db.query(AnalysisHistory).filter(AnalysisHistory.user_id == current_user.id).order_by(AnalysisHistory.timestamp.desc()).limit(100).all()
    return history

@router.post("/analyze")
async def analyze_audio(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    # Validate file format and size
    if not file.filename.lower().endswith(('.wav', '.flac', '.mp3', '.ogg', '.m4a')):
        raise HTTPException(status_code=400, detail="Invalid audio file format")
        
    audio_bytes = await file.read()
    
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
    elif len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file too large (Max 10MB)")
        
    result = run_inference(audio_bytes)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
        
    return result

@router.post("/enroll")
async def enroll_speaker(file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(('.wav', '.flac', '.mp3', '.ogg', '.m4a', '.webm')):
        raise HTTPException(status_code=400, detail="Invalid audio file format")
        
    audio_bytes = await file.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
        
    # Extract audio data (assuming 16kHz mono)
    try:
        audio_file = io.BytesIO(audio_bytes)
        wav, sr = sf.read(audio_file)
        if len(wav.shape) > 1:
            wav = wav.mean(axis=1) # naive mono
        pcm_data = wav.astype(np.float32)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decode audio: {e}")
        
    # Extract embedding
    result = speaker_verification_instance.extract_embedding(pcm_data)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
        
    speaker_id = str(uuid.uuid4())
    
    # Save to db
    profile = db.query(SpeakerProfile).filter(SpeakerProfile.user_id == current_user.id).first()
    if profile:
        speaker_id = profile.id
    else:
        profile = SpeakerProfile(id=speaker_id, user_id=current_user.id)
        db.add(profile)
        db.commit()
        
    save_speaker_embedding(speaker_id, result["embedding"])
    
    return {
        "status": "success",
        "speaker_id": speaker_id,
        "message": "Speaker enrolled successfully."
    }
