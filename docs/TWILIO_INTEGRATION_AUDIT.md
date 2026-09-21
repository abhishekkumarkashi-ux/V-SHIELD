# V-SHIELD — Twilio Live Call Gateway Integration Audit
**Document ID**: `TWILIO-GATEWAY-AUDIT-001`  
**Target Milestone**: Real-Time PSTN / Telephony Live Voice Anti-Spoofing & Biometric Fraud Gateway  
**Date**: September 22, 2026  
**Execution Environment**: Python 3.13.7 (64-bit AMD64) | PyTorch 2.14.0+cpu | ONNX Runtime FP16 | React 18 + Vite  

---

## 1. Executive Summary & Objective

The objective of this initiative is to integrate a carrier-grade **Twilio Voice & Media Stream Gateway** into the existing **V-SHIELD** real-time voice security architecture without breaking, duplicating, or re-architecting any active backend services.

The final operational pipeline will enable:
```
Mobile Phone (PSTN / Cellular)
     │
     ▼
Twilio Inbound Phone Number (+E.164)
     │
     ▼
Twilio Voice Webhook (POST /api/v1/twilio/voice)
     │  [Returns TwiML <Connect><Stream url="wss://PUBLIC_DOMAIN/ws/twilio-stream" />]
     ▼
Twilio Bidirectional Media Stream (WSS /ws/twilio-stream)
     │  [8 kHz μ-law (G.711u) audio chunks, 20ms packets / 160 bytes base64]
     ▼
V-SHIELD FastAPI Telephony Ingestion Worker
     │  [Base64 decode → μ-law decode (audioop-lts) → PCM16 → Resample 8 kHz to 16 kHz mono]
     ▼
Per-Call Isolated Circular Sliding Buffer (AudioCircularBuffer)
     │  [Call SID mapped: Capacity = 64,600 samples (~4.04s), Hop = 8,000 samples (~0.5s)]
     ▼
Voice Activity Detection Guard (MarginPreservingVAD)
     │  [300ms ambient silence margin preservation]
     ▼
Trained V-SHIELD AASIST Anti-Spoofing Engine (ONNX FP16 / PyTorch)
     │  [P(spoof) raw logits & softmax probability]
     ▼
ECAPA-TDNN Biometric Speaker Verification (ONNX FP16 / SpeechBrain)
     │  [192-dim embedding cosine similarity vs enrolled caller profile or NO_REFERENCE]
     ▼
V-SHIELD Dynamic Multi-Signal Risk Engine (RiskEngine)
     │  [EMA smoothing (α = 0.70), explainable factors, 0-100 risk score, automated MFA decision]
     ▼
Real-Time Telemetry Broadcast (/ws/live-call)
     │
     ▼
V-SHIELD React Security Operations Dashboard
```

---

## 2. Current Architecture & Codebase Discovery

A full structural audit of the repository was conducted across `backend/`, `frontend/`, `tests/`, and `scripts/`.

### 2.1 Core Backend Components

| Component | File Path | Status / Implementation Details |
| :--- | :--- | :--- |
| **FastAPI Entry Point** | [`backend/app/main.py`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/main.py) | Sole instance of `FastAPI(title="V-SHIELD Voice Security Platform", version=1.0.0)`. Mounts routers, manages CORS, handles lifespan banners, and hosts existing WebSockets. |
| **Backend Startup Command** | CLI / Powershell | `cd backend; .\venv\Scripts\activate; uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` |
| **Configuration & Hyperparameters** | [`backend/app/config.py`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/config.py) | Pydantic `BaseSettings` reading `.env`. Contains audio thresholds (`SAMPLE_RATE=16000`, `NARROWBAND_SAMPLE_RATE=8000`, `WINDOW_SIZE=64600`, `HOP_SIZE=8000`), risk alpha (`0.70`), and Twilio Verify credentials. |
| **Existing API Routers** | `backend/app/routers/` | 1. `analyze.py` (`POST /api/v1/analyze-file`)<br>2. `auth.py` (`POST /api/v1/auth/login`, `/token`, `/session`, `GET /me`)<br>3. `mfa.py` (`POST /api/v1/mfa/verify-code`, `/dispatch`, `GET /cooldown`) |
| **Existing Direct Endpoints** | [`backend/app/main.py`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/main.py) | `GET /health`, `GET /api/health`, `GET /api/speakers`, `POST /api/speakers/enroll` |
| **Existing WebSocket Endpoints** | [`backend/app/main.py`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/main.py) | `/ws/live-call` and alias `/ws/analyze`. Ingests binary Float32/PCM16 audio chunks, enforces HMAC-SHA256 JWT auth, tracks `AnalysisSession`, broadcasts `TelemetryPacket`. |
| **Audio Circular Buffer** | [`backend/app/core/buffer.py`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/core/buffer.py) | `AudioCircularBuffer`: Thread-safe sliding ring buffer. Capacity = 64,600 samples, hop = 8,000 samples. Supports `append_pcm16_bytes()`, `append_float32_bytes()`, `append_samples()`, and `extract_all_ready_windows()`. |
| **VAD Engine** | [`backend/app/core/vad.py`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/core/vad.py) | `MarginPreservingVAD`: Preserves 300ms ambient silence margins around speech frames to prevent ASVspoof silence-shortcut vulnerabilities. |
| **AASIST Anti-Spoofing Service** | [`backend/app/models/aasist_service.py`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/models/aasist_service.py) | Singleton `AASISTService.get_instance()` with dual-runtime acceleration: Primary ONNX Runtime FP16 (`weights/aasist_fp16.onnx`), secondary PyTorch GNN (`weights/AASIST.pth`). Exposes `predict(audio) -> (logits, spoof_prob)` and `predict_spoof_prob(audio_np) -> float`. |
| **ECAPA Speaker Biometrics** | [`backend/app/models/ecapa_service.py`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/models/ecapa_service.py) | Singleton `ECAPAService.get_instance()` extracting 192-dim embeddings via ONNX Runtime FP16 (`weights/ecapa_fp16.onnx`) or SpeechBrain (`speechbrain_model/`). Persists profiles to SQLite (`vshield.db`). Method `verify_speaker_detailed()` returns `VERIFIED`, `MISMATCH`, `EVALUATING`, `NO_VOICEPRINT`. |
| **Dynamic Risk Engine** | [`backend/app/core/risk_engine.py`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/core/risk_engine.py) | `RiskEngine`: Authoritative multi-signal fusion combining $P(\text{spoof})$, biometric similarity, and VAD speech state. Computes instantaneous 0-100 score, applies EMA smoothing ($\alpha = 0.70$), generates factor explanations, and evaluates automated MFA dispatch conditions. |
| **Out-of-Band MFA Service** | [`backend/app/core/mfa_service.py`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/core/mfa_service.py) | `MFAService`: Singleton managing Twilio Verify API out-of-band challenge dispatching with 120-second sliding cooldown and development OTP simulation fallback. |
| **Session & Auth Core** | [`backend/app/core/auth.py`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/core/auth.py) | HMAC-SHA256 JWT validation, `AnalysisSession` state machine (`is_active`, `record_activity`, `validate_can_accept_audio()`), and error taxonomy (`UNAUTHORIZED`, `SESSION_NOT_ACTIVE`, `EXPIRED_SESSION`). |
| **Database** | `backend/app/vshield.db` | Embedded SQLite database storing enrolled caller voiceprint embeddings. |

---

### 2.2 Frontend Architecture

| Component | File Path | Status / Implementation Details |
| :--- | :--- | :--- |
| **Main Application** | [`frontend/src/App.tsx`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/frontend/src/App.tsx) | Live Call Ingestion tab, File Upload Analysis tab, Risk Gauge, Audio Waveform, Telemetry Breakdown, Mitigation Alert. Health polling runs every 5s. |
| **WebSocket Telemetry Hook** | [`frontend/src/hooks/useVShieldSocket.ts`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/frontend/src/hooks/useVShieldSocket.ts) | Connects to `ws://localhost:8000/ws/live-call`, handles `session_started`, `session_stopped`, `session_reset`, error codes, and receives streaming `TelemetryPacket`. |
| **Vite Dev Server & Proxy** | [`frontend/vite.config.ts`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/frontend/vite.config.ts) | Correctly proxies `/health`, `/api`, and `/ws` (with `ws: true`) to `http://localhost:8000`. |
| **API Client** | [`frontend/src/services/api.ts`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/frontend/src/services/api.ts) | Handles `fetchHealth()` with proxy fallback, `fetchSpeakers()`, and JWT token acquisition. |

---

## 3. Duplicate and Obsolete Code Audit

A search across the workspace for duplicate implementations revealed:
- **No duplicate `FastAPI()` instances**: Only one application is instantiated in `backend/app/main.py`.
- **No second Risk Engine**: `backend/app/core/risk_engine.py` is the single source of truth across tests and routers.
- **No obsolete `ml/` directory**: Machine learning weights and services reside exclusively inside `backend/app/models/` and `backend/app/weights/`.
- **No duplicate Audio Buffers**: Only `backend/app/core/buffer.py` exists.
- **All 104 existing tests pass** with 87.92% statement coverage.

---

## 4. Dependencies & Python 3.13 Telephony Considerations

### 4.1 Audioop Removal in Python 3.13
Python 3.13 removed the standard library `audioop` module. Twilio Media Streams send audio encoded as **8 kHz μ-law (G.711u)**.
- For decoding μ-law bytes into linear signed 16-bit PCM: `audioop-lts` is the official Python 3.13 backport package providing `audioop.ulaw2lin(chunk, 2)`.
- Verification check showed `audioop` is absent in `backend/venv`.
- **Resolution**: Install `audioop-lts` in Phase 2 and add to `backend/requirements.txt`.

### 4.2 Twilio Python SDK
- Used for generating valid TwiML responses (`twilio.twiml.voice_response.VoiceResponse`, `<Connect>`, `<Stream>`) and validating cryptographic webhook request signatures (`RequestValidator`).
- **Resolution**: Add `twilio` to `backend/requirements.txt` in Phase 2.

---

## 5. Files to Modify and Files to Create

### 5.1 Files to Create
1. [`docs/TWILIO_INTEGRATION_AUDIT.md`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/docs/TWILIO_INTEGRATION_AUDIT.md) *(This audit document)*
2. [`backend/app/routers/twilio.py`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/routers/twilio.py) *(Twilio Voice Webhook & Media Stream router)*
3. [`.env.example`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/.env.example) *(Template including `TWILIO_PUBLIC_BASE_URL` and credentials)*
4. [`tests/test_twilio_gateway.py`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/tests/test_twilio_gateway.py) *(Unit & integration tests for TwiML, μ-law conversion, call state lifecycle, and signature validation)*
5. [`docs/TWILIO_SETUP.md`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/docs/TWILIO_SETUP.md) *(Operator configuration manual)*
6. [`docs/TWILIO_ARCHITECTURE.md`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/docs/TWILIO_ARCHITECTURE.md) *(Detailed telephony data flow)*
7. [`docs/TWILIO_IMPLEMENTATION_REPORT.md`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/docs/TWILIO_IMPLEMENTATION_REPORT.md) *(Final report)*

### 5.2 Files to Modify
1. [`backend/requirements.txt`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/requirements.txt): Add `audioop-lts` and `twilio`.
2. [`backend/app/config.py`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/config.py): Add `TWILIO_PUBLIC_BASE_URL: Optional[str] = None`.
3. [`backend/app/main.py`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/main.py): Mount `twilio_router`.
4. [`frontend/src/App.tsx`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/frontend/src/App.tsx) & [`frontend/src/hooks/useVShieldSocket.ts`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/frontend/src/hooks/useVShieldSocket.ts): Wire telephony live telemetry events (`call_sid`, active telephone call status) to the UI.

---

## 6. Detailed Integration Strategy

### 6.1 Call-Specific State Isolation (`call_states`)
Never share a single audio buffer between concurrent incoming calls.
The router will maintain a thread-safe registry:
```python
class CallSessionState:
    call_sid: str
    stream_sid: str
    buffer: AudioCircularBuffer
    vad: MarginPreservingVAD
    risk_engine: RiskEngine
    enrolled_speaker_id: Optional[str]
    created_at: float
    last_packet_time: float

call_states: Dict[str, CallSessionState] = {}
```
- **On `start` event**: Allocate fresh `CallSessionState` for `callSid`.
- **On `media` event**: Decode base64 payload $\to$ μ-law $\to$ signed PCM16 $\to$ resample 8 kHz to 16 kHz $\to$ append to `buffer`. When sliding hop (8,000 samples) is ready $\to$ invoke AASIST $\to$ invoke ECAPA $\to$ invoke RiskEngine $\to$ broadcast telemetry.
- **On `stop` event or disconnect**: Remove `call_states[call_sid]` and invoke `buffer.reset()`.

### 6.2 Latency Characteristics & Sliding Window Timing
- AASIST input window: 64,600 samples @ 16 kHz = **4.0375 seconds**.
- Sliding hop: 8,000 samples @ 16 kHz = **0.5 seconds**.
- Twilio transmits 20ms chunks of 8 kHz audio (160 samples per chunk, which upsamples to 320 samples @ 16 kHz).
- **First inference trigger**: Occurs after accumulating 64,600 samples (approximately 4.04 seconds of speech).
- **Subsequent inferences**: Occur every 0.5 seconds (every 25 Twilio chunks).
- *Documentation rule*: Under no circumstances will the system claim 0.5s time-to-first-detection. The first window requires 4.04s to prime.

### 6.3 Speaker Biometrics & `NO_REFERENCE` Policy
- If an incoming phone call is linked to an enrolled executive (e.g. via caller ID lookup or dashboard parameter), ECAPA performs biometric verification.
- If no reference profile is associated, ECAPA returns `speaker_verification_status = "NO_REFERENCE"` and `speaker_similarity = None`.
- `RiskEngine` directly supports this via its Case 2 branch (`Unenrolled / Unknown Caller`).

### 6.4 Telemetry Bridging to React Dashboard
- A dashboard operator monitoring the live system connects via `/ws/live-call`.
- As Twilio processes incoming telephone audio on `/ws/twilio-stream`, calculated telemetry packets containing `call_sid`, `risk_score`, `metrics`, and `recommended_action` are broadcast to active dashboard subscribers.

### 6.5 Security & Privacy Protections
- **Webhook Signature Validation**: Twilio's `X-Twilio-Signature` is validated using `RequestValidator(TWILIO_AUTH_TOKEN)`.
- **Ephemeral Audio**: Raw audio frames are processed entirely in memory. Once sliding windows are evaluated, raw audio is purged. No raw telephony recordings are written to disk or logged to console.
- **Secret Isolation**: All credentials remain strictly in `.env`.

---

## 7. Pre-Implementation Checklist

- [x] Phase 0: Git safety snapshot captured. Clean working tree on branch `feature/twilio-live-gateway`.
- [x] Phase 1: Full repository audit complete. Single FastAPI instance and single Risk Engine verified.
- [x] Python 3.13 audioop gap diagnosed (`audioop-lts` identified).
- [x] Test suite baselined (104 tests passed, 87.92% coverage).
- [ ] Phase 2: Install `audioop-lts` and `twilio` and update requirements.
- [ ] Phase 3: Create `backend/app/api/twilio.py` (or `backend/app/routers/twilio.py`).
- [ ] Phase 4: Implement `POST /api/v1/twilio/voice` TwiML webhook.
- [ ] Phase 5: Implement `WS /ws/twilio-stream` Media Stream ingestion.

---
*Audit completed and certified by V-SHIELD Systems Engineering.*
