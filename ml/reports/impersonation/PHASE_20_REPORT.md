# PHASE 20 REPORT: Impersonation Risk Engine

## 1. Executive Summary
Phase 20 introduces the **V-SHIELD Impersonation Risk Engine**, a stateful, explainable decision engine that fuses evidence from multiple AI models (Anti-Spoofing and Speaker Verification). Instead of relying on a single inference point, it evaluates bounded temporal windows of audio chunks, manages distinct speaker states, and provides granular risk levels accompanied by explainable evidence. 

## 2. Existing Architecture (Phase 19)
Previously, the backend used a naive `RiskEngine` that computed a simple Exponential Moving Average (EMA) of the spoof probability. If speaker verification found a mismatch (`similarity < 0.25`), it blindly clamped the risk score to `0.85` (CRITICAL). This architecture suffered from:
- Lack of explainability (no distinct reasons).
- Conflation of "spoofed voice" vs. "wrong speaker".
- No hysteresis (the score could bounce instantly).

## 3. New Impersonation Architecture
The new architecture sits centrally in `ml/impersonation/` and separates concerns:
- **`config.py`**: Centralized weights, thresholds, and cooldowns.
- **`evidence.py`**: Strongly typed data models representing a single inference window (chunk).
- **`temporal.py`**: A sliding window queue (e.g., last 30 windows) tracking spoof probabilities, safe/suspicious occurrences, and persistence.
- **`decision.py`**: The rule-engine that derives `base_risk`, translates states into explainable `risk_reasons`, and bounds the `risk_confidence`.
- **`engine.py`**: The main orchestrator handling input parsing, EMA smoothing, and risk payload generation.

## 4. Signal Integration
The engine ingests:
1. **Anti-Spoofing Signal**: Evaluated dynamically using an EMA over the last $N$ windows to suppress instantaneous noise.
2. **Speaker Verification Signal**: Processed strictly only when the speaker is properly enrolled. Similarity $< 0.25$ indicates an imposter.
3. **Temporal Evidence**: Assesses the *persistence* of the threat. A single anomaly causes a slight rise, while repeated threats escalate the confidence and risk level dramatically.

## 5. Development Weights & Configurations
- **MAX_HISTORY_WINDOWS**: `30` (approx 15 seconds)
- **RISK THRESHOLDS**: `LOW: 30`, `MEDIUM: 60`, `HIGH: 80`
- **TEMPORAL ESCALATION THRESHOLD**: `3` (consecutive windows to boost risk).
- **ALERT COOLDOWN**: `10 seconds`.

## 6. Risk Output Structure
```json
{
    "impersonation_risk_score": 85.0,
    "impersonation_risk_level": "CRITICAL",
    "risk_confidence": "HIGH",
    "speaker_status": "NOT_VERIFIED",
    "risk_reasons": [
        "Strong impersonation evidence",
        "Low similarity to enrolled speaker",
        "High synthetic-voice probability",
        "Suspicious evidence persisted across multiple windows"
    ]
}
```

## 7. State Machine and Alert Mechanism
Risk does not oscillate rapidly. The temporal engine requires persistent safe windows to actively decay from a `CRITICAL` state. 
Additionally, the WebSocket integration natively filters out silence (via VAD). When a critical state is achieved, the engine yields an `IMPERSONATION_RISK` alert event. An internal debouncer ensures clients are not spammed with duplicate events within the cooldown window.

## 8. Frontend & WebSocket Changes
- The frontend `LiveAnalysis.tsx` was fully refactored.
- It explicitly distinguishes between "Spoofed Voice" and "Speaker Similarity".
- It surfaces the new explainable `risk_reasons` directly on the dashboard, making it immediately clear *why* the system escalated the risk.

## 9. Security & Privacy
- **Validation**: Incoming `spoof_probability` and `similarity` are clamped to safe boundaries (`[0,1]` and `[-1,1]`), explicitly rejecting `NaN/Inf`.
- **Privacy**: The engine strictly receives inferred features and floats, never raw audio. All state instances are locally scoped to the active WebSocket session, assuring multi-client isolation.

## 10. Test Results
The engine was comprehensively tested using 12 strict edge-case unit tests and a deterministic simulator validating the following 6 behaviors:
- **Scenario A (Genuine)**: Safely classified as LOW risk.
- **Scenario B (AI-gen enrolled)**: CRITICAL risk due to synthetic traits, despite speaker match.
- **Scenario C (Genuine different)**: CRITICAL risk strictly due to persistent speaker mismatch.
- **Scenario D (AI-gen different)**: CRITICAL risk flagging both spoofed and mismatched evidence.
- **Scenario E (Noisy speaker)**: Hysteresis correctly dampened the anomaly, escalating to MEDIUM/HIGH but decaying back to LOW smoothly.
- **Scenario F (Short speech)**: Processed safely with MEDIUM risk and limited `LOW` confidence due to insufficient audio for verification.

## 11. Known Limitations & Next Phases
- **Development Weights**: Current bounds and EMA alpha (0.3) are mathematically robust for testing but not statistically calibrated to a massive real-world dataset.
- **Next Recommended Phase**: The current risk engine operates beautifully on the local dashboard. The immediate next logical step is to deploy this robust architecture as an actual interceptor logic module for real communication platforms (e.g., Phone Call Interception / SIP trunking integration) or cloud deployment (Phase 21+).

> **Note**: This system estimates impersonation risk strictly using acoustic anomalies and verification. It does *not* claim absolute fraud probability without further real-world calibration.
