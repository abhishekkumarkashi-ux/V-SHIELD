"""
V-SHIELD Static Audio Analysis Router (SIH 2026).
POST /api/v1/analyze-file: Processes uploaded reference & test audio files,
runs AASIST anti-spoofing and ECAPA-TDNN speaker verification, and returns
the calculated 0-100 Impersonation Risk Score in JSON format.
"""

from typing import Optional

import numpy as np
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.config import settings
from app.core.audio_processor import (
    load_audio_from_bytes,
    preprocess_static_audio,
    resample_to_mono_16k,
)
from app.core.mfa_service import MFAService
from app.core.risk_engine import RiskEngine
from app.models.aasist_service import AASISTService
from app.models.ecapa_service import ECAPAService
from app.schemas.telemetry import AnalyzeFileResponse, AnalyzeTelemetry

router = APIRouter(tags=["Audio Analysis"])

aasist_service = AASISTService.get_instance()
ecapa_service = ECAPAService.get_instance()
risk_engine = RiskEngine()
mfa_service = MFAService.get_instance()


@router.post("/analyze-file", response_model=AnalyzeFileResponse)
async def analyze_file(
    reference_audio: UploadFile = File(
        ..., description="Trusted audio clip of the genuine speaker"
    ),
    test_audio: UploadFile = File(
        ..., description="Suspicious audio clip to be analyzed for impersonation"
    ),
    phone_number: Optional[str] = Form(
        None, description="Optional target phone for MFA dispatch if high risk"
    ),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> AnalyzeFileResponse:
    """
    Analyzes uploaded static audio files for AI generation and impersonation fraud.

    1. Resamples both files to 16 kHz mono.
    2. Extracts 192-dim baseline voiceprint embedding from reference_audio (ECAPA-TDNN).
    3. Repeat-pads or truncates test_audio to exactly 64,600 samples per ASVspoof standards with 300ms VAD margins.
    4. Computes P(spoof) via AASIST and Cosine Similarity via ECAPA-TDNN.
    5. Fuses metrics into a dynamic 0-100 Impersonation Risk Score.
    """
    # 1. Read input audio payloads
    try:
        ref_bytes = await reference_audio.read()
        test_bytes = await test_audio.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded audio files: {e}")

    if not ref_bytes or len(ref_bytes) < 320:
        raise HTTPException(status_code=400, detail="reference_audio is empty or corrupted.")
    if not test_bytes or len(test_bytes) < 320:
        raise HTTPException(status_code=400, detail="test_audio is empty or corrupted.")

    # 2. Preprocess Reference Audio (Genuine Speaker Baseline)
    try:
        raw_ref_wav, ref_sr = load_audio_from_bytes(ref_bytes)
        ref_16k = resample_to_mono_16k(raw_ref_wav, sr=ref_sr, target_sr=16000)
        ref_embedding = ecapa_service.extract_embedding(ref_16k)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to process reference_audio: {e}")

    # 3. Preprocess Test Audio (Suspicious Sample)
    # - Resample to 16 kHz mono
    # - Retain 300ms ambient silence margins (VAD rule)
    # - Repeat-pad or truncate to exactly 64,600 samples (ASVspoof standard)
    try:
        test_16k, padded_test_64k = preprocess_static_audio(
            file_bytes=test_bytes, target_sr=16000, target_samples=64600, apply_vad=True
        )
        test_embedding = ecapa_service.extract_embedding(test_16k)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to process test_audio: {e}")

    # 4. Model Inference
    # A. ECAPA-TDNN: Cosine similarity between baseline and test embeddings
    dot_prod = float(np.dot(ref_embedding, test_embedding))
    norm_prod = (np.linalg.norm(ref_embedding) * np.linalg.norm(test_embedding)) + 1e-9
    cosine_sim = float(max(-1.0, min(1.0, dot_prod / norm_prod)))

    # B. AASIST: Pass (1, 64600) tensor and calculate P(spoof) = Softmax(logits)[1]
    try:
        _, spoof_prob = aasist_service.predict(padded_test_64k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AASIST inference failure: {e}")

    # 5. Risk Engine Classification
    risk_score, classification, message = risk_engine.classify_static_file(
        spoof_prob=spoof_prob, speaker_similarity=cosine_sim
    )

    # Automated Layer 5 Out-of-Band MFA Dispatch via BackgroundTasks
    if risk_score >= 75.0 or classification == "HIGH_RISK_CLONE":
        target_phone = phone_number or settings.DEFAULT_MFA_TARGET_PHONE
        background_tasks.add_task(
            mfa_service.dispatch_mfa_challenge,
            target_id="static_file_analysis",
            phone_number=target_phone,
        )

    return AnalyzeFileResponse(
        status="success",
        risk_score=round(risk_score, 1),
        classification=classification,
        telemetry=AnalyzeTelemetry(
            spoof_probability=round(spoof_prob, 4), speaker_similarity=round(cosine_sim, 4)
        ),
        message=message,
    )
