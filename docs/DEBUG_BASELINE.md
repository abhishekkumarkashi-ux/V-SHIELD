# V-SHIELD — Phase 0: Baseline System & Live Pipeline Audit

**Date:** 2026-09-20  
**Repository:** [https://github.com/abhishekkumarkashi-ux/V-SHIELD](https://github.com/abhishekkumarkashi-ux/V-SHIELD)  
**Workspace:** `C:\Users\hp world\V-SHIELD\V-SHIELD`  
**Branch:** `main`

---

## 1. Executive Summary

This document establishes the technical baseline for the V-SHIELD platform prior to functional modifications. It audits the end-to-end live audio ingestion pipeline, FastAPI backend, ONNX Runtime inference engine, and React frontend to diagnose why live analysis displays `OFFLINE`, telemetry metrics stay at `0.0`, and microphone audio does not reliably produce real-time inference results.

---

## 2. Current Architecture Overview

```
                          +----------------------------------------------------+
                          |                 BROWSER CLIENT                     |
                          |  frontend/src/App.tsx                              |
                          |  - Live Call Mode / Static File Upload Mode        |
                          +----------------------------------------------------+
                                      |                             |
                       HTTP /api/health (MISSING)       navigator.mediaDevices.getUserMedia
                       HTTP /api/speakers (GET)         AudioContext (ScriptProcessor 2048)
                                      |                 Float32 -> Int16Array (PCM16)
                                      |                 useAudioStreamer.ts
                                      v                             |
                          +-----------------------+                 | ArrayBuffer (PCM16)
                          |  FastAPI Gateway      |                 v
                          |  backend/app/main.py  |<==== WebSocket: /ws/live-call
                          +-----------------------+
                                      |
                     AudioCircularBuffer (64,600 samples)
                     backend/app/core/buffer.py
                                      |
                     MarginPreservingVAD (300ms ambient margins)
                     backend/app/core/vad.py
                                      |
                     Parallel Inference Execution:
                     +---------------------------------------+
                     | 1. AASIST Anti-Spoofing (ONNX FP16)   | -> P(spoof)
                     |    backend/app/models/aasist_service  |
                     | 2. ECAPA-TDNN Biometrics (ONNX FP16)  | -> Cosine Sim
                     |    backend/app/models/ecapa_service   |
                     +---------------------------------------+
                                      |
                     Multi-Signal Fusion & Dynamic Risk Engine
                     backend/app/core/risk_engine.py (EMA alpha=0.70)
                                      |
                     TelemetryPacket JSON Broadcast (every 8,000 samples / ~0.5s)
                                      |
                                      v
                          +----------------------------------------------------+
                          |  frontend/src/hooks/useVShieldSocket.ts            |
                          |  - TelemetryBreakdown.tsx (AASIST, ECAPA, RMS, ms) |
                          |  - RiskGauge.tsx (0-100 gauge)                     |
                          |  - AudioWaveform.tsx (HTML5 Canvas)                |
                          +----------------------------------------------------+
```

---

## 3. Detailed Component Audit (Items A - S)

### A. How Frontend Starts
- Command: `cd frontend && npm run dev`
- Tooling: Vite 5.4.10, React 18.3.1, TypeScript 5.6.3, Tailwind CSS 3.4.14
- Address: `http://localhost:5173`
- Root runner: `package.json` script `npm run frontend` or `npm start` (via `concurrently`).

### B. How Backend Starts
- Command: `cd backend && .\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- Tooling: Python 3.13.7, FastAPI 0.110+, Uvicorn 0.28+, ONNX Runtime 1.17+, PyTorch 2.2+, SpeechBrain 1.0+
- Address: `http://0.0.0.0:8000`

### C. Actual API URL
- Base URL: `http://localhost:8000`
- Active Endpoints:
  - `GET /api/health`: System health and model readiness
  - `GET /api/speakers`: List registered biometric speaker profiles
  - `POST /api/speakers/enroll`: Register new speaker voiceprint
  - `POST /api/v1/analyze-file`: Static two-channel audio file impersonation analysis
  - `POST /api/v1/mfa/dispatch`: Trigger out-of-band Twilio MFA challenge
  - `POST /api/v1/mfa/verify`: Validate 6-digit OTP

### D. Actual WebSocket URL
- In Backend: `@app.websocket("/ws/live-call")` in [backend/app/main.py](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/main.py#L128)
- In Frontend: `ws://localhost:8000/ws/live-call` in [frontend/src/hooks/useVShieldSocket.ts](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/frontend/src/hooks/useVShieldSocket.ts#L35)
- Note: `/ws/analyze` was the deprecated endpoint name from early prototypes.

### E. Health Endpoint
- Backend provides: `GET /api/health`
- Backend lacks: `GET /health` (returns `404 Not Found`).
- Baseline probe output for `http://localhost:8000/health`:
  ```json
  {"detail": "Not Found"}  // HTTP 404
  ```
- Baseline probe output for `http://localhost:8000/api/health`:
  ```json
  {
    "status": "ONLINE",
    "version": "1.0.0",
    "device": "cpu",
    "aasist_loaded": true,
    "ecapa_loaded": true,
    "enrolled_speakers_count": 3,
    "aasist_onnx_loaded": true,
    "ecapa_onnx_loaded": true
  }
  ```

### F. Authentication Mechanism
- Backend: Currently **None** in the live path. No JWT, session cookie, or bearer token is validated on `/ws/live-call` or REST endpoints.
- Frontend: No login screen or token injection in `App.tsx`.

### G. Session Mechanism
- Per-connection state instantiated inside `websocket_live_call`:
  - `buffer = AudioCircularBuffer(capacity=64600, hop_size=8000, target_sample_rate=16000)`
  - `vad = MarginPreservingVAD(sample_rate=16000, min_silence_padding_sec=0.30)`
  - `risk_engine = RiskEngine(alpha=0.70)`
- No persistent session identifier or replay-attack token validation exists.

### H. Current Audio Capture Implementation
- Located in: [frontend/src/hooks/useAudioStreamer.ts](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/frontend/src/hooks/useAudioStreamer.ts)
- Mechanism: `navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true } })`
- Processing: Uses legacy `ScriptProcessorNode(2048, 1, 1)` on the Web Audio thread.
- Fallback: Includes `startSimulation(type: 'genuine' | 'clone' | 'unknown')` generating mathematical sinusoids.

### I. Current Audio Encoding
- Frontend converts `Float32Array` to 16-bit signed integer linear PCM via `convertFloat32ToPCM16` and sends an `ArrayBuffer` (`Int16Array`).

### J. Current Backend Expected Audio Format
- `backend/app/main.py` lines 163-165:
  ```python
  raw_chunk = message["bytes"]
  buffer.append_pcm16_bytes(raw_chunk, input_sample_rate=sample_rate)
  ```
- In `backend/app/core/buffer.py`:
  ```python
  int16_data = np.frombuffer(pcm_bytes[:valid_len], dtype=np.int16)
  float_data = int16_data.astype(np.float32) / 32768.0
  ```
- **Mismatch**: Phase 4 requires raw 16 kHz Float32 PCM (`np.float32`, 4 bytes/sample) via `AudioWorklet` with browser downsampling.

### K. Current VAD Implementation
- Class: `MarginPreservingVAD` in [backend/app/core/vad.py](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/core/vad.py)
- Sample Rate: 16,000 Hz
- Frame Length: 25ms (400 samples)
- Energy Threshold: RMS > 0.005
- Ambient Margin: Preserves 300ms (4,800 samples) before and after detected speech frames to prevent spectral cutoff distortion in AASIST graph attention.

### L. Current Anti-Spoof Model
- Architecture: AASIST (Automated Audio Spoofing with Integrated Spectro-Temporal Graph Attention Networks)
- PyTorch Definition: [backend/app/models/aasist.py](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/models/aasist.py)
- ONNX Accelerated Model: [backend/app/weights/aasist_fp16.onnx](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/weights/aasist_fp16.onnx) (1.35 MB)
- Service Wrapper: `AASISTService` in [backend/app/models/aasist_service.py](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/models/aasist_service.py)

### M. Current Speaker Verification Model
- Architecture: ECAPA-TDNN (192-dimensional embeddings)
- ONNX Accelerated Model: [backend/app/weights/ecapa_fp16.onnx](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/weights/ecapa_fp16.onnx) (84.1 MB)
- PyTorch Fallback: SpeechBrain `spkrec-ecapa-voxceleb`
- Service Wrapper: `ECAPAService` in [backend/app/models/ecapa_service.py](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/models/ecapa_service.py)
- Persistence: SQLite database at `backend/app/vshield.db`

### N. Current Risk Engine
- Class: `RiskEngine` in [backend/app/core/risk_engine.py](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/backend/app/core/risk_engine.py)
- Formula: Multi-tier rule base + bilinear blend smoothed by EMA ($\alpha = 0.70$).
  - Voice Clone: $P(\text{spoof}) > 0.65$ and $\text{sim} > 0.70 \implies \text{Risk} \ge 78$
  - Synthetic Impersonation: $P(\text{spoof}) > 0.65$ and $\text{sim} \le 0.70 \implies \text{Risk} \ge 80$
  - Genuine Caller: $P(\text{spoof}) < 0.30$ and $\text{sim} > 0.70 \implies \text{Risk} < 28$
  - Wrong Speaker: $P(\text{spoof}) < 0.30$ and $\text{sim} < 0.40 \implies \text{Risk} \in [50, 65]$

### O. Actual Model Files Being Loaded
1. `backend/app/weights/aasist_fp16.onnx` (1,345,561 bytes)
2. `backend/app/weights/AASIST.pth` (1,281,532 bytes)
3. `backend/app/weights/ecapa_fp16.onnx` (84,138,597 bytes)
4. `backend/app/vshield.db` (12,288 bytes)

### P. Whether AASIST is Connected
- Yes, actively bound through `aasist_service.predict(safe_audio)` inside `websocket_live_call` in `backend/app/main.py`.

### Q. Current Model Device: CPU/CUDA
- Device: **CPU** (`torch.cuda.is_available()` is `False` on the host workstation; ONNX Runtime selects `CPUExecutionProvider`).

### R. Existing Tests
- Directory: `tests/`
- Test Files: 6 files, 31 tests.
- Status: **31 passed in 110.83s, 83.24% code coverage**.

### S. Existing Environment Variables
- Handled via `pydantic-settings` in `backend/app/config.py`. All defaults provided in code; no `.env` file currently present.

---

## 4. Discovered Bugs & Root Causes

| # | Bug Symptom | Root Cause | File(s) Involved |
|---|---|---|---|
| 1 | Top-right status shows `OFFLINE` on page load | `App.tsx` top-right status is bound strictly to `isConnected` (WebSocket state). When the page loads, WebSocket is not open until "Start Live Call Stream" is clicked. No polling to `/health` or `/api/health` exists. | `frontend/src/App.tsx:L153-L165` |
| 2 | `/health` returns 404 Not Found | Backend endpoint is mounted at `/api/health`, not `/health`. Vite dev server also has no proxy config for `/health`. | `backend/app/main.py:L66`, `frontend/vite.config.ts` |
| 3 | AASIST Worker stays at `0.0%`, RMS stays at `0.0000`, Latency at `0.0 ms`, Risk at `0.0/100` | `TelemetryBreakdown.tsx` and `App.tsx` use default fallbacks `metrics?.spoof_probability ?? 0.0`, formatting `0.0% NATURAL` and `VERIFIED GENUINE` prior to any analysis. | `frontend/src/components/TelemetryBreakdown.tsx:L14-L17`, `frontend/src/App.tsx:L119-L121` |
| 4 | Buffer Priming Delay (4.04 seconds of silence before any packets) | `AudioCircularBuffer` requires `_total_samples_written >= 64600` (4.0375s) before `can_extract()` returns `True`. During the first 4 seconds of streaming, 0 telemetry packets are emitted. | `backend/app/core/buffer.py:L97-L105` |
| 5 | Audio Format Mismatch | Frontend uses deprecated `ScriptProcessorNode` converting to `Int16Array`. Phase 4 requires Float32 PCM via `AudioWorklet` with browser 16kHz resampling. | `frontend/src/hooks/useAudioStreamer.ts:L23-L77` |
| 6 | Browser Sample Rate Lock | Many browsers ignore `{ sampleRate: 16000 }` on `AudioContext` and force hardware rate (44.1kHz or 48kHz). Without client-side resampling, audio sent to 16kHz buffer is 3x sped up. | `frontend/src/hooks/useAudioStreamer.ts:L46-L48` |
| 7 | WebSocket Protocol Incompleteness | WebSocket lacks formal message protocol (`start`, `stop`, `session_started`, `session_stopped`), error handling for malformed packets, and returns no `audio_error` or `audio_metrics` messages. | `backend/app/main.py:L159-L252` |
| 8 | Unauthenticated Ingestion | `/ws/live-call` accepts connections from any client without validating authentication tokens or active session state. | `backend/app/main.py:L128-L142` |

---

## 5. Startup Commands Reference

- **Backend:**
  ```powershell
  cd "c:\Users\hp world\V-SHIELD\V-SHIELD\backend"
  .\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  ```
- **Frontend:**
  ```powershell
  cd "c:\Users\hp world\V-SHIELD\V-SHIELD\frontend"
  npm run dev
  ```
- **Full Stack:**
  ```powershell
  cd "c:\Users\hp world\V-SHIELD\V-SHIELD"
  npm start
  ```
- **Run Tests:**
  ```powershell
  cd "c:\Users\hp world\V-SHIELD\V-SHIELD"
  .\backend\venv\Scripts\pytest tests/ -v
  ```

---

## 6. Phase 1 Implementation Plan

1. **Add Truthful `/health` and `/api/health` Endpoints:**
   - Mount `/health` and maintain `/api/health`.
   - Return real model loading states:
     ```json
     {
       "status": "ok",
       "model_loaded": true,
       "device": "cpu",
       "anti_spoof_model": "AASIST (ONNX FP16)",
       "speaker_verification_loaded": true
     }
     ```
   - Ensure `model_loaded` evaluates actual initialized state of `AASISTService` and `ECAPAService`, not just server uptime.
2. **Add Informative Backend Startup Banner:**
   - Print Python version, PyTorch version, CUDA status, anti-spoof model status, speaker verification status, and risk engine state on startup.
3. **Capture and Surface Model Loading Exceptions:**
   - Add structured exception logging with full error trace if model files are missing or unreadable.
