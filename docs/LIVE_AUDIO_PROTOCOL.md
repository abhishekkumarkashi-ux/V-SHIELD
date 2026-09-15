# Live Audio Protocol

This document defines the WebSocket communication protocol between the V-SHIELD frontend and backend for real-time live voice analysis.

## Overview

The live voice analysis requires high-fidelity raw audio. Due to browser limitations and performance considerations, we use the `AudioContext` and an `AudioWorkletNode` to capture raw PCM audio directly, bypassing lossy encoding (e.g., WebM/Opus via `MediaRecorder`).

### Audio Format
- **Format:** Raw PCM
- **Encoding:** Float32
- **Channels:** 1 (Mono)
- **Sample Rate:** 16,000 Hz

## Connection

**Endpoint:** `ws://<host>:<port>/ws/analyze`

When a connection is established, the server responds with:
```json
{
  "type": "status",
  "status": "connected"
}
```

## Protocol Messages

The protocol uses two types of WebSocket frames:
1. **JSON Text Frames:** For control messages and status updates.
2. **Binary Frames:** For raw audio data chunks.

### Client to Server

#### 1. Start Analysis (JSON)
Initiates the analysis session and authenticates the user. Must be sent before any audio.

```json
{
  "type": "start",
  "token": "<JWT_TOKEN>"
}
```

#### 2. Audio Data (Binary)
Raw `Float32Array` buffer sent continuously. We currently send chunks of 8000 samples (500ms at 16kHz) to balance latency and network overhead.

#### 3. Stop Analysis (JSON)
Terminates the active session and saves the risk history to the database.

```json
{
  "type": "stop"
}
```

### Server to Client

#### 1. Status Events (JSON)
Sent during connection lifecycle changes.

```json
{
  "type": "status",
  "status": "authenticated",
  "speaker_enrolled": true
}
```

#### 2. Analysis Results (JSON)
Sent continuously as audio is processed. The backend maintains a rolling window of 4 seconds with a 1-second hop (overlap).

**When Speech Detected (Buffering):**
```json
{
  "type": "analysis",
  "status": "buffering",
  "vad": "SPEECH",
  "rms": 0.042,
  "buffer_duration_ms": 1500
}
```

**When Inference Runs (Success):**
```json
{
  "type": "analysis",
  "status": "success",
  "timestamp": "2026-09-14T07:42:00.123Z",
  "window_duration_ms": 4000,
  "vad": "SPEECH",
  "latency_ms": 125,
  "spoof_probability": 0.054,
  "speaker_similarity": 0.88,
  "speaker_status": "MATCH",
  "impersonation_risk_score": 12.5,
  "impersonation_risk_level": "LOW",
  "risk_confidence": "HIGH",
  "risk_reasons": []
}
```

#### 3. Error Events (JSON)
Sent when authentication fails, audio formatting is incorrect, or internal exceptions occur.

```json
{
  "type": "error",
  "message": "Authentication required"
}
```

## Buffering and Inference Strategy

1. The `EnergyVAD` module checks incoming 500ms chunks for speech.
2. If silence, the chunk is dropped.
3. If speech, the chunk is appended to the server-side `audio_buffer`.
4. Once `audio_buffer` reaches 64,000 samples (4 seconds):
   - Inference runs on the 4-second chunk.
   - The buffer drops the oldest 16,000 samples (1-second hop), leaving 48,000 samples for overlap in the next window.
5. The model requires 16,000 * 4 samples. Sending 500ms chunks independently to the model is invalid.

## Authentication and Security
- Authentication token is sent via the `start` JSON message or via `vshield_session` cookies.
- Maximum single binary chunk size is strictly enforced (max 512KB) to prevent malicious memory exhaustion.
