# V-SHIELD Anti-Spoofing Dataset Card

## 1. Supported Benchmark Datasets

The V-SHIELD Phase 2 dataset adapter architecture natively supports three standard anti-spoofing benchmarks:

### A. ASVspoof 2019 Logical Access (LA)
- **Source:** University of Edinburgh, EURECOM, Inria (INTERSPEECH 2019)
- **Primary Domain:** Logical access speech synthesis (TTS) and voice conversion (VC)
- **License:** Open Access Academic / Non-Commercial (Inria / ASVspoof Consortium)
- **Audio Format:** 16,000 Hz, 16-bit linear PCM FLAC
- **Structure:**
  - `Train`: 25,380 utterances (2,580 bonafide, 22,800 spoof across 20 speakers)
  - `Dev`: 24,844 utterances (2,548 bonafide, 22,296 spoof across 20 speakers)
  - `Eval`: 71,237 utterances (7,355 bonafide, 63,882 spoof across 67 speakers)
- **Attack Types:**
  - Train/Dev: A01 to A06 (known neural & waveform concatenation algorithms)
  - Eval: A07 to A19 (unseen speech synthesis and voice conversion algorithms)

### B. ASVspoof 2021 Logical Access (LA) & Deepfake (DF)
- **Source:** ASVspoof 2021 Consortium
- **Primary Domain:** Transcoded, codec-compressed, and lossy transmission telephony deepfakes
- **Audio Format:** 16,000 Hz, FLAC (uncompressed and telephone codec varieties)
- **Evaluation Size:** Over 600,000 evaluation utterances with real transmission impairments

### C. In-The-Wild Deepfake Dataset
- **Source:** Research corpus compiled from real-world celebrity / executive voice deepfakes published online (YouTube, social media)
- **Primary Domain:** Unconstrained acoustic environments, diverse microphones, and recent diffusion vocoders (ElevenLabs, Tortoise, Vall-E)
- **Labels:** Binary (`bona-fide` vs `spoof`)

---

## 2. Standardized Manifest Specification

All supported datasets are mapped via adapters into a unified metadata manifest format stored at `training/data/metadata/metadata.csv`:

| Column | Data Type | Description |
| :--- | :--- | :--- |
| `file_path` | `string` | Absolute or dataset-relative path to audio file |
| `speaker_id` | `string` | Unique speaker identifier |
| `label` | `integer` | Standardized label: `0 = BONAFIDE`, `1 = SPOOF` |
| `label_name` | `string` | Literal class string (`"bonafide"` or `"spoof"`) |
| `attack_type` | `string` | Specific attack code (e.g. `A01`, `bonafide`, `in_the_wild`) |
| `dataset` | `string` | Dataset origin identifier (`ASVspoof2019_LA`, etc.) |
| `split` | `string` | Split designation: `"train"`, `"val"`, `"test"` |
| `sample_rate` | `integer` | Native audio sample rate |
| `duration_seconds`| `float` | Audio duration in seconds |
| `num_samples` | `integer` | Total audio frames |

---

## 3. Speaker Leakage & Split Verification

### Critical Partitioning Rule
To prevent models from memorizing speaker biometric traits rather than genuine acoustic artifacts:
$$\text{Speakers}_{\text{train}} \cap \text{Speakers}_{\text{val}} = \emptyset$$
$$\text{Speakers}_{\text{train}} \cap \text{Speakers}_{\text{test}} = \emptyset$$
$$\text{Speakers}_{\text{val}} \cap \text{Speakers}_{\text{test}} = \emptyset$$

The `training/scripts/split_dataset.py` utility guarantees and mathematically asserts disjointness before any model training begins.

---

## 4. Audio Transformation & Normalization Pipeline

Audio ingested from raw datasets passes through a deterministic pipeline:
1. **Mono Conversion:** $\mathbf{x}_{\text{mono}} = \frac{1}{C}\sum_{c=1}^C \mathbf{x}_c$.
2. **Resampling:** High-precision bandlimited sinc interpolation to exactly 16,000 Hz.
3. **Amplitude Normalization:** $\mathbf{x}_{\text{norm}} = \frac{\mathbf{x}}{\max(|\mathbf{x}|) + \epsilon}$.
4. **Length Standardization:** Sliced or right-padded with zeros to exactly 64,000 samples (4.0 seconds).
5. **Finite Value Sanitization:** Any non-finite float (`NaN` or `Inf`) is clamped to zero.
