# V-SHIELD — Voice Activity Detection (VAD) & Margin Preservation Specification

**Platform:** V-SHIELD Real-Time Voice Impersonation Prevention Gateway (SIH 2026)  
**Component:** `backend/app/core/vad.py` (`MarginPreservingVAD`)  
**Target Ingestion:** 16,000 Hz Mono Linear Float32 PCM  

---

## 1. Executive Summary & Problem Formulation

Standard Voice Activity Detection (VAD) tools (e.g. WebRTC VAD, Silero VAD without margins) aggressively trim all non-speech audio down to strict phoneme and syllable boundaries. While optimal for speech-to-text transcription bandwidth reduction, **aggressive silence trimming catastrophically breaks anti-spoofing models trained on ASVspoof 2019 / 2021**.

### The "Silence Shortcut" Breakdown
- In ASVspoof benchmarks, leading and trailing pauses contain subtle acoustic cues (phase coherence, ambient room impulse response, vocoder priming artifacts, synthesis discontinuity boundaries).
- Stripping silence removes these boundary cues, causing model Minimum Tandem Detection Cost Function (min t-DCF) to collapse (deteriorating from ~0.42 to >0.91).
- In Graph Neural Networks such as **AASIST**, spectro-temporal graph edges depend on continuous temporal transition across 64,600 samples (~4.0375s). Arbitrary chopping introduces hard high-frequency boundary transients that induce false-positive spoof classifications.

---

## 2. VAD System Parameters

| Parameter | Value | Description |
|---|---|---|
| **Sampling Rate ($f_s$)** | `16,000 Hz` | Standard mono rate across frontend AudioWorklet and backend. |
| **Window Size ($N$)** | `64,600 samples` | ~4.0375 seconds; matches exact input tensor dimension required by AASIST. |
| **Hop Size ($H$)** | `8,000 samples` | ~0.500 seconds; cadence at which new sliding-window evaluations occur. |
| **Frame Length ($L_f$)** | `400 samples` (25 ms) | Window duration for short-time RMS energy computation. |
| **Energy Threshold ($\theta_E$)** | `0.005 RMS` | Frame-level energy trigger separating active voice from ambient noise. |
| **Minimum Speech Duration** | `50 ms` (2 frames) | Gating threshold to reject transient clicks, pops, and micro-bursts. |
| **Silence Margin Preservation** | `0.300 s` (300 ms / 4,800 smp) | Leading and trailing ambient padding strictly preserved around detected speech. |
| **Active Speech Ratio Threshold**| `> 0.05` (5%) | Minimum portion of window containing speech to flag `is_speech_active=True`. |

---

## 3. Acoustic Discrimination Matrix

`MarginPreservingVAD` deterministically classifies incoming 64.6k sample frames into speech vs silence:

| Acoustic Input Type | Expected RMS Amplitude | Frame Classification | Window Decision | Risk Engine Handling |
|---|---|---|---|---|
| **Pure Silence** | `0.000` | No active frames | `is_speech_active = False` | Risk capped at 25.0; no false alarms. |
| **Ambient Background Noise** | `0.001 - 0.004` | Frames below $0.005$ | `is_speech_active = False` | Risk capped at 25.0; treated as idle channel. |
| **Microphone Pops / Clicks** | `> 0.500` (transient $< 50$ ms) | Filtered out by `min_speech_frames` | `is_speech_active = False` | Click rejected; silence preserved. |
| **Normal Human Speech** | `0.030 - 0.200` | Frames exceed $0.005$ | `is_speech_active = True` | Full AASIST + ECAPA-TDNN evaluation. |
| **Loud / Shouting Speech** | `0.300 - 0.800` | Frames exceed $0.005$ | `is_speech_active = True` | Full AASIST + ECAPA-TDNN evaluation. |

---

## 4. Pipeline Integration Architecture

```
                       16kHz Float32 PCM
                              │
                              ▼
                 AudioCircularBuffer (64,600)
                              │
               (When primed & hop step ready)
                              ▼
            MarginPreservingVAD.process_window()
           ┌──────────────────┴──────────────────┐
           │                                     │
           ▼                                     ▼
     speech_ratio > 0.05                  safe_audio tensor
     is_speech_active                     (64,600 samples)
           │                                     │
           ▼                                     ▼
     RiskEngine.evaluate()                AASIST & ECAPA
  (Suppresses false alarms               (Evaluates continuous
   during ambient pauses)                 spectro-temporal graphs)
```

---

## 5. Verification & Compliance
- **Unit Tests:** `tests/test_vad_margins.py`
  - `test_vad_margin_preservation_on_isolated_speech`: Validates that $\ge 300$ ms margins are retained before and after speech.
  - `test_vad_pure_silence`: Validates non-activation on zero-energy buffers.
  - `test_vad_continuous_speech`: Validates speech activation on continuous voice signals.
  - `test_vad_discrimination_silence_speech_noise`: Validates matrix across silence, normal voice, loud voice, and background noise.
  - `test_vad_transient_click_rejection`: Validates that transients $< 50$ ms are filtered out.
