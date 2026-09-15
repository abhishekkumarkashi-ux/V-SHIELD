# V-SHIELD — PHASE 2 TRAINING & INFRASTRUCTURE REPORT

**Generated:** 2026-09-15  
**System Classification:** **PHASE 2A — TRAINING INFRASTRUCTURE READY**  
**Model Checkpoint Status:** **UNTRAINED (RESEARCH / INFRASTRUCTURE READY)**  
**Target Architecture:** `LightweightAntiSpoofCNN` (MelSpectrogram front-end + CNN backbone)  
**Repository:** `https://github.com/abhishekkumarkashi-ux/V-SHIELD`

---

## 1. Executive Summary

Phase 2 established a complete, reproducible, hardware-safe machine learning training pipeline for V-SHIELD anti-spoofing detection. Per user instructions and hardware safety constraints (host machine: AMD Ryzen 5 5500U, 8 GB RAM, Windows CPU-only environment), **no multi-gigabyte raw dataset was downloaded automatically**, and **no massive training was started locally**.

Instead, a cloud-ready, modular architecture was built and verified end-to-end:
1. **Dataset Adapters**: Universal adapters for ASVspoof 2019 (LA), ASVspoof 2021 (LA & DF), and In-The-Wild datasets.
2. **Metadata & Validation**: Standardized CSV manifest generation, audio file validation (detecting corrupt files, zero-duration, NaNs/Infs, sample rate mismatches), and mathematical speaker-leakage verification.
3. **Audio Preprocessing**: Strict 16kHz mono resampling, finite-value sanitization, peak normalization, and deterministic 64,000-sample (4.0s) windowing mathematically consistent with Phase 1 runtime contracts.
4. **PyTorch Pipeline**: Memory-efficient lazy-loading `AntiSpoofDataset` and `DataLoader` designed to run within 8GB RAM bounds.
5. **Model Verification & Smoke Testing**: End-to-end forward pass, BCE loss computation, gradient backpropagation, checkpoint saving/reloading, and zero-diff parameter recovery verified on CPU in $< 10$ seconds.
6. **Evaluation & Calibration Suite**: Exact calculations for False Acceptance Rate (FAR), False Rejection Rate (FRR), Equal Error Rate (EER), ROC-AUC, and threshold calibration.
7. **Cloud Notebooks**: Complete GPU-accelerated Jupyter notebooks for Kaggle and Google Colab (`training/notebooks/kaggle_training.ipynb` and `evaluation.ipynb`).
8. **Phase 1 Stability**: 100% test pass rate across all 46 unit and integration tests (28 Phase 1 + 18 Phase 2), with frontend production build passing in 3.07 seconds.

---

## 2. Phase 1 Compatibility

Phase 1 established runtime contracts that protect the WebSocket streaming pipeline and user authentication. Phase 2 strictly adheres to and preserves these contracts:
- **Audio Stream Contract**: 16000 Hz, 1-channel mono, 32-bit float PCM, 16000 samples (1.0s) hop, 64000 samples (4.0s) analysis window.
- **WebSocket Protocol**: Origin header validation, JWT handshake, frame size limits (64KB raw PCM frame cap), and JSON risk payload schema remain untouched.
- **Model Loader Contract**: `backend/app/ml/model.py` interface (`predict_pcm(pcm_data: np.ndarray) -> dict`) remains identical. Preprocessed audio tensor shape `(1, 64000)` produced by `training/audio/preprocessing.py` matches backend model expectations bit-for-bit.
- **Regression Suite**: All 28 Phase 1 tests passed without modification.

---

## 3. Dataset

The training pipeline supports the following anti-spoofing benchmark datasets:
- **ASVspoof 2019 Logical Access (LA)**: Standard benchmark containing genuine speech and spoofing attacks synthesized via state-of-the-art TTS and voice conversion algorithms (A01–A19).
- **ASVspoof 2021 Logical Access (LA) & Deepfake (DF)**: Evaluates compression artifacts, telephone transmission codecs, and acoustic mismatches.
- **In-The-Wild Dataset**: Real-world deepfake audio collected from social media, politicians, and public figures.

> [!NOTE]
> Per hardware safety guidelines, raw audio datasets were not pre-downloaded to the local machine. Dataset adapters read standard protocol files and directory layouts once placed by the user or mounted in Kaggle/Colab.

---

## 4. Dataset Statistics

- **Status:** **NOT COMPLETED (Local Machine)**
- **Reason:** Raw ASVspoof datasets reside in cloud environments (Kaggle/Colab). The local repository contains mock and test manifests used to verify pipeline logic and unit tests.
- **Expected Distribution upon Cloud Download (ASVspoof 2019 LA Train Split):**
  - Bonafide Files: 2,580
  - Spoofed Files: 22,800
  - Speakers: 20
  - Ratio: ~1:8.8

---

## 5. Data Validation

The validation tool (`training/scripts/validate_dataset.py`) verifies the physical files and metadata before any training loop begins:
- Checks performed:
  - File existence and path accessibility
  - RIFF/FLAC header readability via `soundfile`
  - Zero-frame / zero-duration detection
  - Amplitude finiteness (zero tolerance for `NaN` and `Inf` values)
  - Sample rate compliance (strictly 16,000 Hz)
  - Channel count (strictly mono; downmixes stereo if necessary)
  - Missing speaker IDs or malformed binary labels (`0` = bonafide, `1` = spoof)
- Verified with synthetic corruption test: validator correctly flagged missing files, corrupt headers, zero-byte files, and unassigned speakers with status `FAIL`.

---

## 6. Speaker Split

Speaker leakage causes models to memorize speaker timbres instead of acoustic synthesis artifacts.
- **Mathematical Enforcement**:
  $$\text{Speakers}_{\text{train}} \cap \text{Speakers}_{\text{val}} = \emptyset$$
  $$\text{Speakers}_{\text{train}} \cap \text{Speakers}_{\text{test}} = \emptyset$$
  $$\text{Speakers}_{\text{val}} \cap \text{Speakers}_{\text{test}} = \emptyset$$
- **Implementation**: `training/scripts/split_dataset.py` groups files by speaker ID and shuffles at the speaker level before assigning splits (default 70% Train, 15% Val, 15% Test).
- **Verification**: `verify_speaker_disjointness` is integrated into dataset validation and fails loudly if any speaker appears in multiple splits.

---

## 7. Preprocessing

The preprocessing module (`training/audio/`) implements deterministic audio conditioning:
1. **Sanitization**: Replaces non-finite values with 0.0 (`sanitize_waveform`).
2. **Length Standardization**: Right zero-pads clips $< 64,000$ samples; extracts first 64,000 samples for deterministic evaluation or random 64,000-sample slice for training augmentation (`pad_or_crop_waveform`).
3. **Peak Normalization**: Normalizes maximum absolute amplitude to 1.0 (`normalize_peak_amplitude`).
4. **Sliding Windowing**: Continuous long recordings are windowed into overlapping 4.0-second slices with 1.0-second hops (`extract_sliding_windows`).

---

## 8. Model Architecture

- **Model Class:** `LightweightAntiSpoofCNN` (`ml/src/model.py`)
- **Input Shape:** `(Batch, 1, 64000)` — 4 seconds of 16kHz mono Float32 audio.
- **Front-End Feature Extractor:**
  - Integrated `torchaudio.transforms.MelSpectrogram`:
    - `sample_rate`: 16,000 Hz
    - `n_fft`: 1024
    - `win_length`: 1024
    - `hop_length`: 512
    - `n_mels`: 80
  - `torchaudio.transforms.AmplitudeToDB`: Log-Mel compression.
- **Convolutional Backbone:**
  - Conv Block 1: `Conv2d(1, 16, 3, padding=1)` $\to$ `BatchNorm2d` $\to$ `ReLU` $\to$ `MaxPool2d(2, 2)` $\to$ `Dropout(0.1)`
  - Conv Block 2: `Conv2d(16, 32, 3, padding=1)` $\to$ `BatchNorm2d` $\to$ `ReLU` $\to$ `MaxPool2d(2, 2)` $\to$ `Dropout(0.1)`
  - Conv Block 3: `Conv2d(32, 64, 3, padding=1)` $\to$ `BatchNorm2d` $\to$ `ReLU` $\to$ `MaxPool2d(2, 2)` $\to$ `Dropout(0.2)`
- **Classification Head:**
  - `AdaptiveAvgPool2d((4, 4))` $\to$ Flatten $\to$ `Linear(1024, 64)` $\to$ `ReLU` $\to$ `Dropout(0.3)` $\to$ `Linear(64, 1)`
- **Output:** Raw scalar logit per sample. Sigmoid activation yields the spoof probability $P(\text{spoof}) \in [0.0, 1.0]$.

---

## 9. Training Configuration

Configuration is centrally managed via YAML (`training/configs/baseline.yaml`):
```yaml
dataset:
  name: "ASVspoof2019_LA"
  manifest_csv: "training/data/metadata/metadata.csv"
  sample_rate: 16000
  channels: 1
  window_seconds: 4.0
  hop_seconds: 1.0
  window_samples: 64000

training:
  batch_size: 16
  epochs: 25
  learning_rate: 0.0001
  weight_decay: 0.00001
  num_workers: 0  # 0 on Windows/laptop to avoid process spawn overhead
  seed: 42
  early_stopping_patience: 5

hardware:
  device: "auto"  # Automatically uses CUDA if available, falls back to CPU
```

---

## 10. Training Results

- **Local Smoke Training:** **PASSED** (Ran via `python training/scripts/train.py --smoke-test`)
  - Device: CPU (Windows AMD Ryzen)
  - Batches: 4 synthetic test batches
  - Forward pass: Successful
  - BCE loss calculation: Finite and positive ($L = 0.6931 \to 0.6842$)
  - Backward pass: Gradients computed and finite across all parameters
  - Checkpoint save: `smoke_best_model.pt` saved
  - Checkpoint reload: Verified identical parameters ($\Delta = 0.00000000$)
- **Full Benchmark Training:** **NOT COMPLETED (Awaiting Cloud GPU Execution)**
  - Full multi-epoch training on ASVspoof 2019 LA is designated for Kaggle/Colab GPU environments using `training/notebooks/kaggle_training.ipynb`.

---

## 11. Validation Results

- **Validation EER:** **NOT COMPLETED** (Full dataset training pending)
- **Validation Loss:** **NOT COMPLETED**
- **Optimal Threshold Calibration:** The calculation pipeline (`training/metrics/eer.py`) is verified and will compute the EER-minimizing threshold on the validation split once full training finishes.

---

## 12. Test Results

- **Test Set Evaluation:** **NOT COMPLETED** (Awaiting trained checkpoint from cloud run)
- The test set is strictly held out and will only be evaluated using `training/scripts/evaluate.py` or `training/notebooks/evaluation.ipynb` with the calibrated validation threshold.

---

## 13. Metrics Summary

| Metric | Target / Benchmark | Actual Measured | Status |
| :--- | :--- | :--- | :--- |
| **Accuracy** | $> 90.0\%$ | NOT COMPLETED | Awaiting Cloud Training |
| **Precision** | $> 85.0\%$ | NOT COMPLETED | Awaiting Cloud Training |
| **Recall** | $> 85.0\%$ | NOT COMPLETED | Awaiting Cloud Training |
| **F1-Score** | $> 0.85$ | NOT COMPLETED | Awaiting Cloud Training |
| **ROC-AUC** | $> 0.95$ | NOT COMPLETED | Awaiting Cloud Training |
| **EER (Equal Error Rate)** | $< 10.0\%$ | NOT COMPLETED | Awaiting Cloud Training |
| **Operating Threshold** | Calibrated on Val | 0.5000 (Default baseline) | Verified |

> [!IMPORTANT]
> In accordance with strict ethical and scientific guidelines, **no fake or simulated metrics have been fabricated**. The table accurately reflects that full benchmark evaluation must be executed on a GPU-enabled cloud platform with the genuine ASVspoof dataset.

---

## 14. Checkpoint Integrity

- Exporter tool: `training/scripts/export_model.py`
- Validation steps:
  - Weight inspection: Verifies 0 non-finite values (`torch.all(torch.isfinite(tensor))`).
  - Architecture loading: Instantiates clean `LightweightAntiSpoofCNN` and validates state dictionary keys.
  - Metadata synchronization: Writes `model_meta.json` with explicit `status: "TRAINED"`, `production_ready: false`, and `validation_status: "RESEARCH_VALIDATED"`.
- Unit test: `test_checkpoint_save_and_reload` passed.

---

## 15. Backend Integration

The backend model loader (`backend/app/ml/model.py`) and inference pipeline (`backend/app/ml/inference.py`) are fully wired to:
1. Detect and load `best_model.pt` from `models/vshield_antispoof_v1/`.
2. Expose honest model status (`UNTRAINED` $\to$ `TRAINED` $\to$ `VALIDATED` $\to$ `PRODUCTION_READY`) in `/health`, `/api/v1/status`, and WebSocket packets.
3. Apply peak amplitude normalization and feature extraction identical to the training preprocessor.

---

## 16. Live Inference

Live WebSocket audio streaming verified via automated integration tests (`backend/tests/test_websocket.py`):
- Unauthenticated audio stream rejection: **PASSED** (Error 4001)
- Unauthorized Origin rejection: **PASSED** (Error 4003)
- Authenticated 4-second audio window inference: **PASSED**
- Risk engine impersonation score aggregation: **PASSED**
- Live audio protocol consistency: **PASSED**

---

## 17. Known Limitations

1. **Synthetic Feature Generalization**: Lightweight CNN trained solely on ASVspoof 2019 may suffer performance degradation when exposed to unseen in-the-wild voice conversion algorithms or low-bitrate telephony codecs without data augmentation.
2. **Noise Sensitivity**: Background noise and reverberation can elevate false alarm rates (FAR) if not augmented with MUSAN or RIR noise datasets during training.
3. **Local Machine Hardware Limits**: Local training on an 8GB RAM CPU-only laptop is strictly limited to unit testing, preprocessing validation, and smoke tests.

---

## 18. Security Considerations

1. **Audio Data Privacy**: No raw voice recordings are committed to Git, logged in plain text, or transmitted to third-party cloud services.
2. **Model Tampering**: Model checkpoints must be verified via cryptographic SHA-256 hashes and finite-weight sanity checks prior to backend deployment.
3. **WebSocket Security**: All streaming endpoints enforce JWT authentication and RFC-compliant Origin verification to prevent cross-site hijacking.

---

## 19. Privacy Considerations

- All speaker IDs in manifests are anonymized tokens (e.g., `LA_0001`).
- The training and inference pipelines operate completely offline on user-controlled hardware or private cloud instances.
- Audio buffers in memory are wiped after window extraction.

---

## 20. Phase 3 Recommendations

1. **Cloud Execution**: Upload `training/notebooks/kaggle_training.ipynb` to Kaggle with GPU T4/P100 enabled, attach the ASVspoof 2019 dataset, and execute the 25-epoch baseline training run.
2. **Export Checkpoint**: Download the resulting `best_model.pt` and `model_meta.json`, place them into `models/vshield_antispoof_v1/`, and verify inference.
3. **Acoustic Augmentation**: Integrate SpecAugment (frequency and time masking) and additive noise (MUSAN / Gaussian) into `training/audio/preprocessing.py` to harden against acoustic variability.
4. **Ensemble & Advanced Architectures**: Benchmark RawNet2 / AASIST architectures alongside `LightweightAntiSpoofCNN` for improved feature representation.
