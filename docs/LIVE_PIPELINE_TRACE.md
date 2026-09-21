# V-SHIELD — Real-Time Live Pipeline Static Trace Specification

**Architecture Specification:** End-to-End Live Voice Security Pipeline  
**Version:** Production Hardened 1.0.0  
**Phase:** Phase 24 System Audit

---

## Complete Runtime Trace: File → Function → Next Function

```
[MICROPHONE]
   │
   ▼
1. frontend/src/audio/AudioCapture.ts: AudioCapture.start()
   ├── navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, ... } })
   ├── AudioContext initialization (hardware native sample rate)
   ├── createMediaStreamSource(stream) -> createAnalyser()
   └── AudioWorkletNode setup (fallback: ScriptProcessorNode.onaudioprocess)
   │
   ▼
2. frontend/src/audio/AudioCapture.ts: AudioCapture.handleRawSamples()
   ├── resampleFloat32Audio(rawInput, hardwareRate, 16000) [Linear Interpolation]
   ├── Accumulate in resampleBuffer
   └── Slices into 2048-sample frames -> onAudioChunk(chunk.buffer, debugInfo)
   │
   ▼
3. frontend/src/services/api.ts: ensureAuthToken()
   ├── POST /api/v1/auth/login (username: analyst@vshield.internal)
   └── localStorage.setItem('vshield_auth_token', access_token)
   │
   ▼
4. frontend/src/hooks/useVShieldSocket.ts: useVShieldSocket.connect()
   ├── new WebSocket("ws://localhost:8000/ws/live-call?token=<JWT>&speaker_id=<ID>")
   ├── ws.binaryType = 'arraybuffer'
   └── ws.onopen: ws.send(JSON.stringify({ type: 'start', format: 'float32', token: tokenToUse }))
   │
   ▼
5. frontend/src/hooks/useAudioStreamer.ts -> useVShieldSocket.sendAudioChunk()
   └── ws.send(pcmChunk) [Raw Binary Float32Array ArrayBuffer]
   │
   ▼
6. backend/app/main.py: websocket_live_call() [@app.websocket("/ws/live-call")]
   ├── Extracts query/header/cookie/subprotocol candidate_token
   ├── backend/app/core/auth.py: verify_access_token(candidate_token)
   │     └── Validates HMAC-SHA256 signature and expiration
   ├── Rejects unauthorized / expired sessions (close code 1008)
   └── Initializes AnalysisSession(session_id, user_id, username, role)
   │
   ▼
7. backend/app/main.py: Audio Ingestion Loop [while True: message = await websocket.receive()]
   ├── analysis_session.validate_can_accept_audio()
   ├── np.frombuffer(raw_chunk, dtype=np.float32) [with finite & amplitude bounds check]
   └── np.clip(audio_samples, -1.0, 1.0)
   │
   ▼
8. backend/app/core/buffer.py: AudioCircularBuffer.append_samples()
   ├── Stores audio samples in ring buffer (capacity: 64,600 samples, hop: 8,000 samples)
   └── If not primed (< 64,600): reports AudioMetricsPacket(pipeline_status="LISTENING", status="warming_up", buffered_seconds, required_seconds)
   │
   ▼
9. backend/app/core/buffer.py: AudioCircularBuffer.extract_all_ready_windows()
   └── Extracts ready window tensors (length: 64,600 samples = 4.0375s at 16 kHz)
   │
   ▼
10. backend/app/core/vad.py: MarginPreservingVAD.process_window()
    ├── Energy RMS thresholding across 20ms frames
    ├── Preserves 300 ms ambient silence margins before and after speech clusters
    └── Returns (is_speech_active, speech_ratio, safe_audio)
   │
   ▼
11. backend/app/models/aasist_service.py: AASISTService.predict()
    ├── Feeds safe_audio (1, 64600) into AASIST Graph Attention Network (ONNX Runtime / PyTorch)
    └── Returns (raw_logits, spoof_prob)
   │
   ▼
12. backend/app/models/ecapa_service.py: ECAPAService.verify_speaker_detailed()
    ├── Extracts 192-dimensional embedding via SpeechBrain ECAPA-TDNN / ONNX
    ├── Cosine similarity comparison against SQLite enrolled profile
    └── If no enrolled profile: status="NO_VOICEPRINT", similarity=None
   │
   ▼
13. backend/app/core/risk_engine.py: RiskEngine.evaluate_detailed()
    ├── compute_instantaneous_risk(spoof_prob, speaker_similarity, is_speech_active)
    ├── Exponential Moving Average smoothing (alpha = 0.70)
    ├── Threat Classification: BONA_FIDE_GENUINE, WRONG_SPEAKER, HIGH_RISK_CLONE, SYNTHETIC_IMPERSONATION
    └── Factor decomposition for explainability
   │
   ▼
14. backend/app/main.py: Layer 5 Mitigation & MFA Check
    ├── RiskEngine.should_trigger_mfa(risk_score, recommended_action)
    ├── High-confidence attack (P(spoof) >= 0.80) or 2-window debounce
    └── backend/app/core/mfa_service.py: MFAService.dispatch_mfa_challenge() [120s sliding cooldown]
   │
   ▼
15. backend/app/main.py: Telemetry Broadcast
    ├── Constructs TelemetryPacket(timestamp, risk_score, metrics, classification, recommended_action, mfa_status)
    └── await websocket.send_text(json.dumps(packet_dict))
   │
   ▼
16. frontend/src/hooks/useVShieldSocket.ts: ws.onmessage()
    ├── Parses JSON payload
    ├── Handles audio_metrics -> setServerAudioMetrics(data)
    └── Handles analysis -> setLatestPacket(data), setPipelineStatus("ANALYZING"), setHistory(...)
   │
   ▼
17. frontend/src/App.tsx: React Dashboard Rendering
    ├── RiskGauge.tsx: Renders dynamic animated 0-100 SVG gauge
    ├── AudioWaveform.tsx: Visualizes live microphone waveform from AnalyserNode
    ├── TelemetryBreakdown.tsx: Renders factor explainability bars & latency stats
    └── MitigationAlert.tsx: Renders active mitigation banner and out-of-band MFA status
```
