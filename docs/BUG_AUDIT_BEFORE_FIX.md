# V-SHIELD — Pre-Fix Bug & Architecture Audit Report

**Date:** 2026-09-22  
**Baseline Commit:** `008f439`  
**Git Branch:** `main`  
**Working Tree:** Clean (verified zero uncommitted user modifications)  

---

## 1. Executive Summary

A comprehensive architectural and security audit of the V-SHIELD repository was executed across the backend, frontend, ML models, CI workflows, and test suites prior to applying fixes. While the test suite passes locally with 115 tests and 87.82% coverage, critical quality gates (ruff, black, flake8) currently fail, and significant architectural vulnerabilities exist in WebSocket authentication, secret management, CORS configuration, and ML fallback mechanisms.

---

## 2. Current Architecture Overview

```
Client / Dashboard (React + Vite + TypeScript)
  │
  ├── REST APIs (/api/v1/auth, /api/v1/mfa, /api/v1/analyze-file, /api/v1/twilio)
  └── WebSockets (/ws/live-call, /ws/analyze, /ws/twilio-stream)
        │
        ▼
  FastAPI Backend (backend/app/main.py)
        │
        ├── Auth Guard (RFC 7519 JWT HMAC-SHA256 & Session Lifecycle)
        ├── Audio Ingestion (PCM16 / Float32 16 kHz Mono & 8 kHz Telephony)
        ├── Circular Ring Buffer (64,600 sample window / 8,000 sample hop)
        ├── Margin-Preserving VAD (300ms ambient silence padding)
        ├── AASIST GNN Anti-Spoofing (ONNX Runtime FP16 + PyTorch Fallback)
        ├── ECAPA-TDNN Biometric Verification (ONNX Runtime FP16 + SpeechBrain)
        ├── Multi-Signal Risk Engine (EMA α=0.70 Fusion & Threat Classification)
        └── Layer 5 Automated Out-of-Band MFA Dispatch (Twilio Verify)
```

---

## 3. Test & Quality Gate Baseline

| Quality Gate / Test Suite | Command | Baseline Status | Details |
|---|---|---|---|
| **Pytest Unit & Integration** | `pytest tests/ -v --cov=backend/app` | **PASS (115/115)** | Execution time: 194s, 35 warnings |
| **Backend Coverage** | `--cov-fail-under=80` | **PASS (87.82%)** | Exceeds 80% threshold requirement |
| **Ruff Linter** | `ruff check backend/app tests/` | **FAIL (17 errors)** | Unused imports in `twilio.py`, `test_phase13_e2e_pipeline.py`, `test_twilio_gateway.py` |
| **Black Code Formatter** | `black --check backend/app tests/` | **FAIL (11 files)** | 11 files require reformatting |
| **Flake8 Linter** | `flake8 backend/app tests/` | **FAIL (15 errors)** | Unused imports and trailing blank lines |
| **Frontend TypeScript** | `npm run lint` (`tsc --noEmit`) | **PASS** | 0 type errors |
| **Frontend Vite Build** | `npm run build` | **PASS** | Distribution generated in 8.29s |

---

## 4. Security Findings & Secret Audit

1. **Hardcoded Secrets & Passwords in Source Code:**
   - `backend/app/config.py`: Hardcoded `JWT_SECRET_KEY = "vshield-production-core-security-secret-key-sih2026-auth"`.
   - `backend/app/config.py`: Hardcoded `DEFAULT_MFA_TARGET_PHONE = "+919876543210"`.
   - `backend/app/core/auth.py`: In-memory user database stores pre-hashed passwords for default accounts (`analyst@vshield.internal`, `operator@vshield.internal`, `admin@vshield.internal`, and fallback console accounts `operator` and `analyst` with password `"vshield"`).
   - **Remediation Action:** Flag historically committed credentials as compromised. Require environment variables for production (`JWT_SECRET_KEY`, `DEMO_OPERATOR_PASSWORD`, etc.) with secure random/dev-only fallbacks explicitly marked for development only.

2. **Insecure CORS Configuration:**
   - `backend/app/main.py`: Configures `allow_origins=settings.CORS_ORIGINS` (defaults to `["*"]`) while `allow_credentials=True`. Browsers reject credentialed requests with wildcard origins, and wildcard CORS with credentials constitutes a security vulnerability.
   - **Remediation Action:** Restrict `CORS_ORIGINS` to validated origins (e.g. `http://localhost:5173`, `http://127.0.0.1:5173`, production frontend origin) and enforce environment variable override.

3. **WebSocket Authentication Bypass & Zombie Connections:**
   - `backend/app/main.py` (`/ws/live-call` & `/ws/analyze`): `await websocket.accept()` is executed **before** authenticating the token. If an unauthenticated client connects with no token, the socket remains open; errors are only pushed upon receiving subsequent frames.
   - **Remediation Action:** Implement strict pre-accept/handshake authentication. Reject unauthenticated or expired connections immediately with WS code 1008 (Policy Violation) and invalidate inactive sessions.

---

## 5. Machine Learning Pipeline Findings

1. **Incompatible ECAPA Handcrafted Acoustic Fallback:**
   - `backend/app/models/ecapa_service.py`: When neither ONNX Runtime nor SpeechBrain is loaded, `extract_embedding` falls back to a handcrafted 192-dimensional vector constructed from FFT spectral moments, autocorrelation, and zero-crossing rates. Handcrafted acoustic features are mathematically incompatible with real ECAPA-TDNN latent embeddings and produce invalid similarity scores.
   - **Remediation Action:** Remove the fake 192-d acoustic generator. If ECAPA is unavailable, set `speaker_verification_status = "UNAVAILABLE"`, return `None` for similarity, and propagate this status to the risk engine without faking biometrics.

2. **Fake Pre-Seeded Default Speaker Profiles:**
   - `backend/app/models/ecapa_service.py` (`_seed_default_speakers`): Automatically creates three fake speaker profiles (`exec-001`, `exec-002`, `exec-003`) with random Gaussian vectors (`rng.randn(192)`).
   - **Remediation Action:** Remove fake speaker generation. If no genuine speaker has enrolled, `get_enrolled_speakers()` must return an empty list and indicate `NO_VOICEPRINT`.

3. **Non-Deterministic Runtime Weights Download:**
   - `backend/app/models/aasist_service.py` (`_ensure_weights`): Attempts to download `AASIST.pth` from GitHub via `urllib.request` at runtime if the file is missing or `< 100,000` bytes.
   - **Remediation Action:** Remove runtime network download. Inspect local files, validate file presence, and expose explicit status (`READY`, `NOT_READY`, `LOAD_ERROR`).

4. **Missing Warm-Up State in Real-Time Streaming:**
   - AASIST requires 64,600 samples (~4.04s @ 16 kHz). During buffer priming, the pipeline should not emit Risk=0; it must emit explicit `status: "warming_up"` with `buffered_seconds` and `required_seconds`.

---

## 6. CI/CD Workflow Findings

- `.github/workflows/ci.yml` runs three jobs:
  1. `code-quality`: Ruff, Black, Flake8. **Will fail on main right now due to linter and formatting issues.**
  2. `test-backend`: Audio headers (`libsndfile1 ffmpeg`), CPU PyTorch, backend requirements, pytest with `--cov-fail-under=80`.
  3. `test-frontend`: `npm ci`, `npm run lint`, `npm run build`.
- **Action Plan:** Resolve all Ruff, Black, and Flake8 errors across `backend/app` and `tests/` without lowering standards, verify clean dependency resolution, and test all CI jobs locally before pushing.
