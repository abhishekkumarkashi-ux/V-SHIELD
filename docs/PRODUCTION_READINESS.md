# V-SHIELD — Production Readiness & Architecture Specification

**Project:** V-SHIELD — Real-time AI Voice Security / Anti-Spoofing Web Application  
**Version:** 1.0.0 Production Hardened  
**Date:** September 2026 (SIH 2026)

---

## 1. System Architecture

V-SHIELD provides real-time voice anti-spoofing, synthetic speech detection, and speaker identity verification over both browser WebSockets and live telecom gateways (Twilio PSTN/cellular):

```
Client Stream (Browser WebRTC / Twilio μ-law 8 kHz)
   │
   ▼
Ingestion Gateway
   ├── /ws/live-call (WebSocket, authenticated via Bearer / Subprotocol / In-band)
   └── /api/v1/twilio/stream (μ-law 8 kHz -> PCM16 16 kHz Polyphase Upsampler)
   │
   ▼
Isolated Ring Buffer (AudioCircularBuffer)
   ├── Window: 64,600 samples (~4.0375s at 16 kHz)
   ├── Hop: 8,000 samples (~0.5s sliding increment)
   └── Warm-Up Tracking: explicit status="warming_up", buffered_seconds, required_seconds
   │
   ▼
Acoustic Preprocessing & VAD Guard
   └── MarginPreservingVAD: 300 ms ambient silence margin retention (ASVspoof 2021 compliant)
   │
   ▼
Multi-Model Parallel Inference Engine
   ├── AASIST (Integrated Spectro-Temporal Graph Attention Network) -> P(spoof)
   └── ECAPA-TDNN (SpeechBrain 192-dim VoxCeleb Embeddings) -> Cosine Similarity
   │
   ▼
Multi-Signal Risk Fusion Engine (RiskEngine)
   ├── Exponential Moving Average (EMA alpha = 0.70)
   ├── Risk Score: 0 - 100 with explainable factor decomposition
   └── Threat Classifications: BONA_FIDE_GENUINE, WRONG_SPEAKER, HIGH_RISK_CLONE, SYNTHETIC_IMPERSONATION
   │
   ▼
Layer 5 Mitigation & Out-of-Band MFA
   ├── High-confidence attack bypass (P(spoof) >= 0.80) or 2-window debounce
   ├── Sliding Cooldown: 120-second suppression of repeated challenge dispatch
   └── Real Twilio Verify SMS / Outbound Voice OTP (with dev simulation fallback)
   │
   ▼
Live Dashboard Broadcast
   └── React + Vite + TypeScript Real-time Telemetry Dashboard
```

---

## 2. Component Verification Matrix: REAL vs DEMO vs UNAVAILABLE

| Component | Status | Implementation Details |
|---|---|---|
| **AASIST Anti-Spoofing** | **REAL** | Native PyTorch Graph Attention Network (`AASIST.pth`) + ONNX Runtime FP16 execution engine. Deterministic loading without runtime web downloads. If checkpoint missing, explicitly flags `LOAD_ERROR` / `NOT_READY`. |
| **ECAPA Speaker Verification** | **REAL** | `speechbrain/spkrec-ecapa-voxceleb` extracting 192-dimensional embeddings. Persisted in SQLite `vshield.db`. Fake random profile generation (`exec-001`) and handcrafted acoustic FFT fallbacks removed. Missing voiceprint returns `status: "NO_VOICEPRINT"`. |
| **Ring Buffer & VAD** | **REAL** | NumPy circular buffer with FIFO extraction and 300 ms ambient silence padding preservation. |
| **Risk Engine** | **REAL** | Bilinear multi-signal fusion with EMA smoothing. Silence or missing model emits `INSUFFICIENT_DATA` / `risk_score: None`, never masking errors as safe. |
| **Twilio Live Call Gateway** | **REAL** | TwiML webhook generator + WebSocket audio processor with μ-law decoding and polyphase upsampling. |
| **MFA Verification** | **REAL / CONFIGURABLE** | Twilio Verify API when credentials provided; secure in-memory simulator when unconfigured for local development. |
| **Authentication** | **REAL** | HMAC-SHA256 JWT tokens with PBKDF2 credential verification, role-based access control, and active session tracking. |

---

## 3. Environment Variables & Security Configuration

Production configurations MUST be supplied via environment variables (`.env` or container environment). Insecure default values are strictly rejected in production mode (`ENVIRONMENT=production`).

| Variable | Type | Description | Production Requirement |
|---|---|---|---|
| `ENVIRONMENT` | string | `production` or `development` | Default: `development` |
| `JWT_SECRET_KEY` | string | Cryptographic secret for signing JWT access tokens | **Required** in production |
| `DEMO_OPERATOR_USERNAME` | string | Operator username for console login | Default: `analyst@vshield.internal` |
| `DEMO_OPERATOR_PASSWORD` | string | Password for operator login | **Required** in production |
| `CORS_ORIGINS` | list/str | Allowed HTTP and WebSocket origins | Disallows wildcard `*` with credentials |
| `DEFAULT_MFA_TARGET_PHONE` | string | Fallback phone number for out-of-band MFA | Optional (defaults to simulated) |
| `TWILIO_ACCOUNT_SID` | string | Twilio Account SID for telephony | Required if using live Twilio |
| `TWILIO_AUTH_TOKEN` | string | Twilio Auth Token | Required if using live Twilio |
| `TWILIO_VERIFY_SERVICE_SID`| string | Twilio Verify Service SID for SMS/call OTP | Required for live Twilio MFA |
| `TWILIO_PUBLIC_BASE_URL` | string | Public HTTPS domain (e.g. ngrok or cloud domain) | Required for Twilio webhook TwiML |
| `MFA_COOLDOWN_SECONDS` | int | Debounce cooldown between automated MFA dispatches | Default: `120` seconds |

---

## 4. WebSocket Protocols & Authentication

### 4.1 Connection Handshake Authentication
Clients connecting to `/ws/live-call` or `/ws/analyze` must provide authentication credentials via any of the following channels:
1. **Query Parameter:** `ws://host:8000/ws/live-call?token=<JWT>`
2. **Authorization Header:** `Authorization: Bearer <JWT>`
3. **Cookie:** `access_token=<JWT>`
4. **WebSocket Subprotocol:** `Sec-WebSocket-Protocol: vshield-token.<JWT>`

### 4.2 In-Band Authentication Flow
Standard browser WebSocket APIs cannot send custom headers. V-SHIELD provides an in-band authentication protocol:
1. Client connects to `/ws/live-call`.
2. Client sends:
   ```json
   { "type": "auth", "token": "<JWT>" }
   ```
3. Backend responds:
   ```json
   { "type": "authenticated", "user": { "username": "analyst@vshield.internal", "role": "operator" } }
   ```
4. If a client attempts to transmit binary audio or control frames prior to authenticating, the server rejects the message with:
   ```json
   { "type": "auth_error", "code": "UNAUTHORIZED", "message": "Authentication required" }
   ```

### 4.3 Warm-Up State Semantics
AASIST requires 64,600 samples (~4.04 seconds at 16 kHz) before emitting its first inference window. During this period:
- `AudioMetricsPacket` reports:
  ```json
  {
    "type": "audio_metrics",
    "pipeline_status": "LISTENING",
    "status": "warming_up",
    "buffered_seconds": 2.1,
    "required_seconds": 4.04
  }
  ```
- No premature `risk_score = 0` is emitted during warm-up.

---

## 5. Local Setup & CI Verification

### 5.1 Backend Setup
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate  # or source venv/bin/activate on Linux/macOS
pip install -r requirements.txt
```

### 5.2 Quality Gates & Automated Tests
Execute the exact steps run by GitHub Actions CI:
```bash
# 1. Linters & Formatting
ruff check backend/app tests/
black --check backend/app tests/
flake8 backend/app tests/

# 2. Automated Pytest Suite with >= 80% Coverage Enforcement
pytest tests/ -v --cov=backend/app --cov-report=term-missing --cov-fail-under=80
```

### 5.3 Frontend Verification
```bash
cd frontend
npm ci
npm run lint   # tsc --noEmit
npm run build  # vite build
```

---

## 6. Known Production Boundaries & Limitations

1. **Hardware Acceleration:** AASIST ONNX Runtime executes on CUDA when available with automated fallback to multithreaded CPU. On CPU-only environments, per-hop inference latency is ~120–180 ms.
2. **Audio Alignment:** Streaming audio must be 16-bit PCM mono or 32-bit Float mono at 16 kHz (or μ-law 8 kHz when received via the Twilio gateway).
3. **MFA Delivery:** Twilio Verify integration requires active carrier SMS connectivity; when disabled or unconfigured, the system automatically falls back to in-memory simulation without blocking pipeline telemetry.
