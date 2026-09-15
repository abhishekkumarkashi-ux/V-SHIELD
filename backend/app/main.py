import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router
from app.api.auth import router as auth_router
from app.websocket.audio_stream import router as ws_router
from app.database.database import engine, Base, ensure_schema_compatibility

# Create tables and ensure schema compatibility
if engine:
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility(engine)

app = FastAPI(
    title="V-SHIELD API",
    description="AI-powered real-time voice security platform",
    version="1.0.0"
)

# CORS configuration
allowed_origins_raw = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175,http://localhost:3000,http://127.0.0.1:3000"
)
cors_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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
    
    # Create development user if not exists
    from app.database.database import SessionLocal
    from app.database.models import User
    import bcrypt
    
    if SessionLocal:
        db = SessionLocal()
        try:
            dev_user = db.query(User).filter(User.email == "dev@vshield.app").first()
            if not dev_user:
                hashed_pw = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                new_user = User(
                    email="dev@vshield.app",
                    name="Developer User",
                    hashed_password=hashed_pw
                )
                db.add(new_user)
                db.commit()
                print("Created seed user dev@vshield.app with password admin123")
        except Exception as e:
            print(f"Error seeding user: {e}")
        finally:
            db.close()

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
    status = "ok"
    if not model_instance.is_loaded:
        status = "degraded"
    
    return {
        "status": status,
        "model_loaded": model_instance.is_loaded,
        "model_status": getattr(model_instance, "model_status", "UNKNOWN"),
        "production_ready": getattr(model_instance, "production_ready", False),
        "validation_status": getattr(model_instance, "validation_status", "NOT_VALIDATED"),
        "model_disclaimer": getattr(model_instance, "model_disclaimer", "Anti-spoofing model is not validated for production use."),
        "model_error": "checkpoint not found or failed to load" if not model_instance.is_loaded else None,
        "speaker_model_loaded": getattr(speaker_verification_instance, "is_loaded", True),
        "device": str(model_instance.device),
        "websocket": "available"
    }

