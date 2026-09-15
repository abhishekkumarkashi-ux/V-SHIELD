# V-SHIELD Anti-Spoofing Model Card

## 1. Model Overview
- **Model Name:** `vshield_antispoof_v1`
- **Architecture:** `LightweightAntiSpoofCNN`
- **Model Type:** Acoustic Binary Classifier (Bonafide vs. Spoof)
- **Input Representation:** Raw 16,000 Hz Mono Float32 PCM waveform `(Batch, 1, 64000)` (4.0 seconds duration)
- **Output:** Uncalibrated scalar logit $\rightarrow$ Sigmoid probability $P(\text{spoof}) \in [0.0, 1.0]$
- **Framework:** PyTorch 2.x & Torchaudio

---

## 2. Intended Use & Scope
- **Primary Use Case:** Real-time telephony and voice stream analysis to detect AI-generated voice cloning, deepfake audio, text-to-speech (TTS), and voice conversion (VC) attacks.
- **System Integration:** Operates in tandem with SpeechBrain ECAPA-TDNN speaker verification and stateful risk scoring (`ImpersonationEngine`).
- **Target Latency:** $< 20\text{ ms}$ on CPU per 4.0-second window.
- **Out-of-Scope / Non-Intended Use:** 
  - Must **not** be used as a standalone single-factor authentication authorization mechanism for high-value financial transactions.
  - Not calibrated for acoustic environments with Signal-to-Noise Ratio (SNR) $< 5\text{ dB}$.

---

## 3. Architecture & Feature Extraction
1. **Differentiable Log-Mel Front-End:**
   - Sample Rate: 16,000 Hz
   - Window Size (`n_fft`): 512 samples (32 ms)
   - Hop Length: 160 samples (10 ms)
   - Mel Filterbanks (`n_mels`): 80 bins
   - Amplitude Scaling: Decibel scale (`AmplitudeToDB`)
2. **Backbone Conv2D Feature Extractor:**
   - Block 1: $\text{Conv2d}(1 \rightarrow 16, 3\times 3) + \text{BatchNorm} + \text{ReLU} + \text{MaxPool}(2\times 2)$
   - Block 2: $\text{Conv2d}(16 \rightarrow 32, 3\times 3) + \text{BatchNorm} + \text{ReLU} + \text{MaxPool}(2\times 2)$
   - Block 3: $\text{Conv2d}(32 \rightarrow 64, 3\times 3) + \text{BatchNorm} + \text{ReLU} + \text{MaxPool}(2\times 2)$
3. **Temporal Invariance:**
   - $\text{AdaptiveAvgPool2d}((1, 1))$ compresses variable temporal duration into 64 fixed dimensional latent vectors.
4. **Classifier Head:**
   - $\text{Linear}(64 \rightarrow 32) + \text{ReLU} + \text{Dropout}(0.5) + \text{Linear}(32 \rightarrow 1)$.

---

## 4. Training & Preprocessing Protocol
- **Audio Preprocessing:**
  - Resampling to 16,000 Hz via polyphase sinc interpolation.
  - Conversion of multi-channel streams to mono by channel averaging.
  - Peak amplitude normalization: $x = x / \max(|x|)$.
  - Fixed 64,000-sample windowing: random crop during training; deterministic front crop during inference.
- **Loss Function:** Binary Cross Entropy with Logits (`nn.BCEWithLogitsLoss`), supporting positive class weighting for unbalanced datasets.
- **Optimization:** Adam optimizer ($\text{lr} = 3 \times 10^{-4}$, weight decay $= 1 \times 10^{-4}$, gradient norm clipping $= 5.0$).
- **Validation:** Minimum Equal Error Rate (EER) early stopping with patience of 5 epochs.

---

## 5. Evaluation Methodology & Metrics
- **Speaker Disjointness:** Strictly enforced: $\text{Speakers}_{\text{train}} \cap \text{Speakers}_{\text{val}} = \emptyset$ and $\text{Speakers}_{\text{train}} \cap \text{Speakers}_{\text{test}} = \emptyset$.
- **Primary Benchmark Metric:** Equal Error Rate (EER) — the operating point where False Alarm Rate equals False Rejection Rate ($\text{FAR} = \text{FRR}$).
- **Secondary Metrics:** Area Under the ROC Curve (ROC-AUC), Precision, Recall, F1 Score.
- **Threshold Policy:** The operating threshold $\tau$ is calibrated **exclusively on the validation split** to achieve EER. The calibrated threshold is then applied without re-tuning to the held-out test split.

---

## 6. Known Failure Modes & Limitations
1. **Unseen Generative Vocoders:** Novel neural vocoder architectures not present in the training corpus can exhibit reduced detection accuracy.
2. **Codec Compression Artifacts:** Heavy lossy compression (e.g., AMR-NB, low-bitrate Opus $< 12\text{ kbps}$) can introduce high-frequency phase smearing that may trigger elevated false positive rates.
3. **Acoustic Distortion & Clipping:** Severe microphone preamp clipping alters harmonic ratios, potentially skewing log-mel distributions.
4. **Hardware Environment:** Inference is tuned for FP32 on CPU. When running on low-resource microcontrollers, latency may exceed streaming budgets.

---

## 7. Security, Privacy & Ethics
- **Data Privacy:** Raw user audio is never written to disk during live WebSocket inference; audio chunks are processed in ephemeral memory buffers.
- **Adversarial Robustness:** Direct gradient-based adversarial perturbations on raw PCM can degrade confidence. Multi-layer defense in depth (VAD + ECAPA-TDNN biometric verification + EMA temporal risk smoothing) mitigates isolated frame attacks.
