from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router
from app.api.auth import router as auth_router
from app.websocket.audio_stream import router as ws_router
from app.database.database import engine, Base

# Create tables
if engine:
    Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="V-SHIELD API",
    description="AI-powered real-time voice security platform",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from app.ml.model import model_instance
from app.ml.speaker_verification import speaker_verification_instance
import os

@app.on_event("startup")
async def startup_event():
    # Load model exactly once at startup
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    model_path = os.path.join(base_dir, 'models', 'vshield_antispoof_v1', 'best_model.pt')
    model_instance.load_model(model_path)
    
    # Load Speaker Verification Model
    speaker_verification_instance.load_model()

app.include_router(api_router)
app.include_router(auth_router)
app.include_router(ws_router)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "V-SHIELD Backend",
        "version": "1.0.0"
    }

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": model_instance.is_loaded,
        "device": str(model_instance.device)
    }
