# V-SHIELD — Twilio Live Telephone Call Gateway Architecture

**Document ID**: `TWILIO-ARCH-2026`  
**System**: V-SHIELD Real-Time Voice Impersonation Defense & Telephony Fraud Prevention Platform  

---

## 1. End-to-End Architecture Overview

The Twilio Live Call Gateway integrates traditional cellular and PSTN telephone networks directly into V-SHIELD's AI inference and multi-signal risk fusion engine.

```
                    CELLULAR / PSTN TELEPHONY
                              │
                    [Mobile / Landline Phone]
                              │ Dial Number
                              ▼
                      [Twilio Platform]
                              │
                              ├─────────────────────────────────────────┐
                              ▼                                         ▼
                 [Inbound Voice Webhook]                      [Media Stream WebSocket]
               POST /api/v1/twilio/voice                       WSS /ws/twilio-stream
                              │                                         │
                   Returns TwiML <Connect>                              │ (8 kHz μ-law chunks)
                   <Stream url="wss://..." />                           │ 20ms / 160 samples
                              │                                         ▼
                              └──────────────────────────────► [Base64 Decoding]
                                                                        │
                                                                        ▼
                                                             [μ-law G.711u Decode]
                                                            (audioop.ulaw2lin 16-bit)
                                                                        │
                                                                        ▼
                                                            [Polyphase Resampling]
                                                             8 kHz -> 16 kHz Mono
                                                                        │
                                                                        ▼
                                                          [Isolated AudioCircularBuffer]
                                                              (call_states[call_sid])
                                                          Window: 64,600 samples (~4.04s)
                                                          Hop:     8,000 samples (~0.50s)
                                                                        │
                                      ┌─────────────────────────────────┴─────────────────────────────────┐
                                      ▼                                                                   ▼
                          [MarginPreservingVAD]                                               [Sliding Hop Extraction]
                         300ms Ambient Preservation                                           Yields (1, 64600) Tensor
                                      │                                                                   │
                                      └─────────────────────────────────┬─────────────────────────────────┘
                                                                        ▼
                                                    [AASIST Anti-Spoofing Model]
                                                    ONNX Runtime FP16 / PyTorch GNN
                                                       Raw Logits -> Softmax P(spoof)
                                                                        │
                                                                        ▼
                                                  [ECAPA-TDNN Speaker Biometrics]
                                                  192-dim Voiceprint Cosine Similarity
                                                    (Enrolled vs NO_REFERENCE)
                                                                        │
                                                                        ▼
                                                    [Dynamic Multi-Signal RiskEngine]
                                                    Exponential Moving Average (α=0.70)
                                                    Instantaneous -> Fused Score [0-100]
                                                    Action: ALLOW / STEP_UP / MFA / QUARANTINE
                                                                        │
                                      ┌─────────────────────────────────┴─────────────────────────────────┐
                                      ▼                                                                   ▼
                         [Out-of-Band MFA Service]                                            [Live Telemetry Broadcast]
                        Automated Twilio Verify SMS                                           WSS /ws/live-call (JSON)
                         120s Sliding Cooldown                                                            │
                                                                                                          ▼
                                                                                              [React Operations Dashboard]
                                                                                              RiskGauge / Waveform / Actions
```

---

## 2. Component Breakdown & Data Transformations

### 2.1 Stage 1: Inbound Call Signaling (TwiML)
- **Protocol**: HTTP/1.1 POST over TLS.
- **Endpoint**: `/api/v1/twilio/voice`.
- **Security**: Cryptographic HMAC-SHA1 signature validation via `X-Twilio-Signature` using `RequestValidator(TWILIO_AUTH_TOKEN)`.
- **Output**:
  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <Response>
      <Connect>
          <Stream url="wss://vshield-secure.ngrok-free.app/ws/twilio-stream">
              <Parameter name="caller_phone" value="+15551234567" />
              <Parameter name="call_sid" value="CA1234567890abcdef" />
          </Stream>
      </Connect>
  </Response>
  ```

---

### 2.2 Stage 2: Audio Decoding & Resampling
- **Format**: G.711 μ-law, 8,000 Hz, 8-bit mono, 20ms frames (160 bytes per packet).
- **Transport**: JSON payload over WebSocket:
  ```json
  {"event": "media", "sequenceNumber": "42", "media": {"payload": "..."}}
  ```
- **Conversion Pipeline**:
  1. `raw_ulaw = base64.b64decode(payload)` (160 bytes).
  2. `pcm16 = audioop.ulaw2lin(raw_ulaw, 2)` (320 bytes linear signed 16-bit PCM).
  3. `float_samples = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0`.
  4. Polyphase rational upsampling via `scipy.signal.resample_poly(float_samples, up=2, down=1)`:
     $$\text{Length}: 160 \times 2 = 320 \text{ samples at } 16,000 \text{ Hz}.$$

---

### 2.3 Stage 3: Call-Specific Circular Sliding Buffer
- **Isolation Principle**: Every phone call is tracked in `call_states[call_sid]`.
- **Buffer Specifications**:
  - `capacity = 64600` samples ($\approx 4.0375$ seconds at 16 kHz).
  - `hop_size = 8000` samples ($\approx 0.5000$ seconds at 16 kHz).
- **Sliding Timing Dynamics**:
  - The first inference requires accumulation of 64,600 samples ($\approx 202$ Twilio 20ms chunks = 4.04s).
  - Subsequent inferences trigger on every 8,000 samples ($\approx 25$ Twilio 20ms chunks = 0.50s).
  - Guarantees continuous, rolling security assessment while maintaining sufficient acoustic temporal context for AASIST graph attention.

---

### 2.4 Stage 4: Acoustic Anti-Spoofing (AASIST)
- **Model**: AASIST (Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention).
- **Runtime**: ONNX Runtime FP16 with CPU / CUDA execution providers.
- **Input Tensor**: `(1, 64600)` Float32 normalized.
- **Output**: 2-dimensional logits $\to$ Softmax probability:
  $$P(\text{spoof}) = \frac{e^{\text{logit}_{\text{spoof}}}}{e^{\text{logit}_{\text{bonafide}}} + e^{\text{logit}_{\text{spoof}}}} \in [0.0, 1.0].$$

---

### 2.5 Stage 5: Biometric Speaker Verification (ECAPA-TDNN)
- **Model**: SpeechBrain ECAPA-TDNN (Emphasized Channel Attention, Propagation and Aggregation).
- **Output**: 192-dimensional unit-normalized embedding vector.
- **Verification Logic**:
  - If call is associated with an enrolled speaker ID ($E_{\text{enrolled}}$):
    $$\text{Similarity} = \cos(\theta) = \frac{E_{\text{incoming}} \cdot E_{\text{enrolled}}}{\|E_{\text{incoming}}\| \|E_{\text{enrolled}}\|} \in [-1.0, 1.0].$$
    - $\text{Similarity} \ge 0.70 \implies \text{VERIFIED}$.
    - $\text{Similarity} \le 0.40 \implies \text{MISMATCH}$.
    - $0.40 < \text{Similarity} < 0.70 \implies \text{EVALUATING}$.
  - If no voiceprint profile is associated:
    $$\text{speaker\_verification\_status} = \text{"NO\_REFERENCE"},\quad \text{similarity} = \text{None}.$$

---

### 2.6 Stage 6: Multi-Signal Risk Engine
- **Instantaneous Scoring Formulation**:
  - **Enrolled Caller**:
    - Voice Clone Attack ($S > 0.65, V > 0.70$):
      $$R_{\text{instant}} = 78.0 + 12 \left(\frac{S - 0.65}{0.35}\right) + 8 \left(\frac{V - 0.70}{0.30}\right) \in [78.0, 98.0].$$
    - Synthetic Speech ($S > 0.65, V \le 0.70$):
      $$R_{\text{instant}} = 80.0 + 18 \left(\frac{S - 0.65}{0.35}\right) \in [80.0, 98.0].$$
    - Genuine Verified ($S < 0.30, V > 0.70$):
      $$R_{\text{instant}} = \max\left(5.0, 15.0 + 15 \left(\frac{S}{0.30}\right) - 10 \left(\frac{V - 0.70}{0.30}\right)\right) \in [5.0, 28.0].$$
    - Wrong Speaker / Human Imposter ($S < 0.30, V < 0.40$):
      $$R_{\text{instant}} = 52.0 + 12 \left(\frac{0.40 - V}{1.40}\right) \in [52.0, 64.0].$$
  - **Unenrolled Caller ($V = \text{None}$)**:
    - $S > 0.65$: $R_{\text{instant}} = 75.0 + 23 \left(\frac{S - 0.65}{0.35}\right)$.
    - $S < 0.30$: $R_{\text{instant}} = 25 \left(\frac{S}{0.30}\right)$.
    - Ambient Silence ($VAD = \text{False}$): $R_{\text{instant}} = \min(R_{\text{instant}} \times 0.30, 25.0)$.
- **Temporal EMA Smoothing**:
  $$\text{EMA}_t = \alpha \cdot R_{\text{instant}} + (1 - \alpha) \cdot \text{EMA}_{t-1}, \quad \alpha = 0.70.$$

---

### 2.7 Stage 7: Telemetry Streaming & Dashboard
- **Protocol**: JSON text broadcast over `/ws/live-call`.
- **Payload Structure**:
  ```json
  {
    "type": "telemetry",
    "source": "twilio_pstn",
    "call_sid": "CA1234567890abcdef",
    "stream_sid": "MZ1234567890abcdef",
    "caller_phone": "+15551234567",
    "timestamp": 1726967890.123,
    "risk_score": 14.5,
    "classification": "LOW_RISK",
    "decision": "LOW_RISK",
    "factors": [...],
    "metrics": {
      "spoof_probability": 0.0012,
      "speaker_similarity": 0.8621,
      "speaker_status": "VERIFIED",
      "buffer_energy_rms": 0.0482,
      "vad_speech_ratio": 0.94,
      "latency_ms": 942.3
    },
    "recommended_action": "ALLOW_CALL",
    "mfa_status": "NONE",
    "latency": {
      "audio_buffer_ms": 1.1,
      "inference_ms": 780.2,
      "speaker_verification_ms": 160.8,
      "total_ms": 942.1
    }
  }
  ```

---

## 3. Resilience & Memory Lifecycle

1. **Clean Deallocation**: `call_states.pop(call_sid)` is executed in the `stop` event and within the `finally:` block of the WebSocket handler.
2. **Buffer Zeroing**: Explicit memory wipe via `buffer.reset()` releases numpy memory buffers.
3. **Fault Isolation**: An uncaught inference error in Call A generates a structured telemetry notice and does not terminate Call B or the FastAPI worker.
