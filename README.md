# V-SHIELD (SIH 2026 - Problem Statement ID: 26104)
## Real-Time AI Voice Impersonation Detection & Fraud Prevention

V-SHIELD is an enterprise-grade, real-time voice integrity and impersonation defense system. It detects synthetic, cloned, and manipulated audio during ongoing telephone and VoIP calls while simultaneously verifying registered speaker biometrics and computing a dynamic 0–100 Impersonation Risk Score.

---

## 1. Verified Technical Discoveries & Domain Constraints

- **Silence Shortcut Mitigation (ASVspoof 2021 finding):** Models trained on ASVspoof 2019 LA exploit leading and trailing pauses; stripping silence via Voice Activity Detection (VAD) causes error rates to collapse (min t-DCF deteriorates from 0.42 to 0.91+). **Requirement:** Layer 2 VAD strictly preserves **250–300 ms of ambient leading and trailing margins** around active speech segments.
- **Acoustic Front-End:** Uses the official Clova AI AASIST architecture (Integrated Spectro-Temporal Graph Attention Network) trained with `nb_samp = 64600` (~4.04 seconds at 16 kHz).
- **Narrowband Telephony Handling:** Asterisk/PSTN inputs arriving at 8 kHz (μ-law / a-law / GSM) are automatically upsampled to 16 kHz mono prior to inference.
- **Dual-Biometric Verification:** Employs `speechbrain/spkrec-ecapa-voxceleb` (ECAPA-TDNN) for extracting 192-dimensional speaker embeddings and evaluating cosine similarity.

---

## 2. Target System Architecture

```
Layer 1: Audio Ingestion (FastAPI WebSocket /ws/live-call, PCM16 streaming)
  │
Layer 2: Preprocessing & Ring Buffer
  │   ├── VAD Segmenter with 300 ms silence padding retention
  │   └── Sliding Window Buffer (Size = 64,600 samples, Hop = 8,000 samples / 0.5 s)
  │
Layer 3: Parallel AI Analysis Engine
  │   ├── AASIST Worker: Returns synthetic log-odds P(bona_fide) vs P(spoof)
  │   └── ECAPA-TDNN Worker: Cosine similarity vs enrolled user profile
  │
Layer 4: Dynamic Risk Engine
  │   ├── Exponential Moving Average smoothing (alpha = 0.7)
  │   └── Multi-Signal Fusion (0-100 Risk Score)
  │
Layer 5: Decision & Mitigation Trigger (Low: 0-30, Medium: 31-69, High: 70-100)
  │
Frontend: React + TypeScript + Tailwind CSS (Live gauge, telemetry, call actions)
```

---

## 3. Decision & Mitigation Matrix

| Condition | Threat Profile | Dynamic Risk Score | Automated Mitigation Action |
|---|---|---|---|
| $P(\text{spoof}) > 0.65$ & $\text{similarity} > 0.70$ | **Voice Clone Attack** | $\ge 75$ (Crimson) | `TRIGGER_MFA_CALLBACK` |
| $P(\text{spoof}) > 0.65$ & $\text{similarity} \le 0.70$ | **Synthetic Speech** | $\ge 80$ (Crimson) | `TERMINATE_AND_ALERT` / `QUARANTINE` |
| $P(\text{spoof}) < 0.30$ & $\text{similarity} > 0.70$ | **Genuine Caller** | $< 30$ (Emerald) | `ALLOW_CALL` / `MONITOR` |
| $P(\text{spoof}) < 0.30$ & $\text{similarity} < 0.40$ | **Unknown / Imposter** | $50 - 65$ (Amber) | `FLAG_OPERATOR_VERIFICATION` |

---

## 4. WebSocket Contract (`/ws/live-call`)

- **Client Ingests:** Raw binary PCM16 audio chunks (16 kHz, 16-bit mono, little-endian).
- **Server Broadcasts:** Structured JSON telemetry every 8,000 samples (~0.5s):

```json
{
  "timestamp": 1726700000.52,
  "risk_score": 82.4,
  "classification": "HIGH_RISK",
  "metrics": {
    "spoof_probability": 0.89,
    "speaker_similarity": 0.84,
    "buffer_energy_rms": 0.042,
    "vad_speech_ratio": 0.76,
    "latency_ms": 32.5
  },
  "recommended_action": "TRIGGER_MFA_CALLBACK"
}
```

---

## 5. Static File Analysis REST API (`POST /api/v1/analyze-file`)

Accepts multipart audio file uploads to test suspect voice recordings against an enrolled genuine reference:

- **Parameters:**
  - `reference_audio`: Trusted audio file of the genuine speaker (WAV / FLAC / PCM).
  - `test_audio`: Suspicious audio file to analyze for AI synthesis and impersonation.
- **Preprocessing Pipeline:**
  - Resamples to 16 kHz mono (supporting 8 kHz telephony PSTN inputs).
  - Preserves 300 ms ambient silence margins around speech segments.
  - Implements official ASVspoof repeat-padding (looping) for short clips and truncation for clips exceeding 64,600 samples.
- **Example cURL:**
  ```bash
  curl -X POST http://localhost:8000/api/v1/analyze-file \
    -F "reference_audio=@genuine_speaker.wav" \
    -F "test_audio=@suspect_call.wav"
  ```
- **Response Payload:**
  ```json
  {
    "status": "success",
    "risk_score": 88.5,
    "classification": "HIGH_RISK_CLONE",
    "telemetry": {
      "spoof_probability": 0.92,
      "speaker_similarity": 0.81
    },
    "message": "AI-generated voice impersonation detected. MFA recommended."
  }
  ```

---

## 5. Quickstart & Execution

### Option A: Local Development

1. **Backend Setup:**
   ```bash
   cd backend
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Frontend Setup:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Open `http://localhost:5173` to launch the Mission Control Dashboard.

### Option B: Docker Compose
```bash
docker-compose up --build
```

### Option C: Run Unit Tests
```bash
pytest tests/ -v
```
Verifies audio buffer sliding window, VAD 300 ms margin compliance, and risk score calculation logic.
