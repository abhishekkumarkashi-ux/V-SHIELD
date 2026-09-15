# V-SHIELD Anti-Spoofing ML Training Pipeline

This directory contains the production-grade, reproducible training and evaluation pipeline for the V-SHIELD Voice Anti-Spoofing system.

---

## 1. Directory Structure

```text
training/
├── README.md                 # Setup & workflow guide
├── configs/
│   └── baseline.yaml         # Training hyperparameters & model configuration
├── datasets/                 # Dataset adapters & PyTorch DataLoader
│   ├── base.py               # Abstract BaseDatasetAdapter & AudioSampleRecord
│   ├── asvspoof2019.py       # ASVspoof 2019 Logical Access adapter
│   ├── asvspoof2021.py       # ASVspoof 2021 LA / DF adapter
│   ├── in_the_wild.py        # In-The-Wild deepfake speech adapter
│   └── torch_dataset.py      # Lazy-loading PyTorch Dataset & DataLoader
├── audio/                    # Audio loading, resampling & preprocessing
│   ├── loader.py             # Audio I/O & resampling to 16kHz mono
│   ├── preprocessing.py      # Peak normalization & 4-second padding/cropping
│   └── windowing.py          # 4-second sliding window generation (1s hop)
├── metrics/                  # Anti-spoofing evaluation metrics
│   └── eer.py                # Equal Error Rate (EER), ROC-AUC & FAR/FRR
├── scripts/                  # Command-line tools
│   ├── build_manifest.py     # Generate standardized metadata.csv from raw datasets
│   ├── validate_dataset.py   # Audit audio files, format integrity & speaker leakage
│   ├── split_dataset.py      # Partition datasets into speaker-disjoint splits
│   ├── train.py              # Main training script (supports --smoke-test)
│   ├── evaluate.py           # Threshold calibration on Val, test evaluation
│   └── export_model.py       # Export clean checkpoint with model_meta.json
├── checkpoints/              # Model checkpoints (best_model.pt, last_model.pt)
├── reports/                  # Detailed training & evaluation JSON reports
└── notebooks/                # Cloud GPU training notebooks
    ├── kaggle_training.ipynb # Kaggle GPU training notebook
    └── evaluation.ipynb      # Independent evaluation & threshold tuning notebook
```

---

## 2. Dataset Acquisition & Setup

V-SHIELD enforces a strict safety rule: **large 20+ GB datasets are never automatically downloaded to your local drive.**

### Step A: Obtain Dataset
1. **ASVspoof 2019 Logical Access (LA):**
   - Download from the official [Edinburgh DataShare](https://datashare.ed.ac.uk/handle/10283/3336) repository:
     - `LA.zip` containing `ASVspoof2019_LA_train`, `ASVspoof2019_LA_dev`, `ASVspoof2019_LA_eval`, and `ASVspoof2019_LA_cm_protocols`.
2. **In-The-Wild Audio:**
   - Place downloaded wav files in `training/data/raw/InTheWild/` with `meta.csv`.

### Step B: Extract Files
Extract the archive into `training/data/raw/`:
```text
training/data/raw/ASVspoof2019_LA/
├── ASVspoof2019_LA_train/
│   └── flac/
├── ASVspoof2019_LA_dev/
│   └── flac/
├── ASVspoof2019_LA_eval/
│   └── flac/
└── ASVspoof2019_LA_cm_protocols/
    ├── ASVspoof2019.LA.cm.train.trn.txt
    ├── ASVspoof2019.LA.cm.dev.trl.txt
    └── ASVspoof2019.LA.cm.eval.trl.txt
```

---

## 3. Workflow Execution

### Step 1: Generate Standardized Manifest
```bash
python training/scripts/build_manifest.py \
    --dataset-name ASVspoof2019_LA \
    --dataset-root training/data/raw/ASVspoof2019_LA \
    --output-csv training/data/metadata/metadata.csv \
    --splits train dev
```

### Step 2: Validate Dataset Integrity & Speaker Leakage
```bash
python training/scripts/validate_dataset.py \
    --manifest-csv training/data/metadata/metadata.csv
```

### Step 3: Run Fast Smoke Test (Sanity Verification)
Verifies the model forward pass, loss calculation, backward step, optimizer, validation, and checkpoint reloading without requiring a large dataset:
```bash
python training/scripts/train.py --smoke-test
```

### Step 4: Train on GPU (Cloud: Kaggle / Google Colab)
For training on large datasets, use the GPU notebooks located in `training/notebooks/`:
- Open `training/notebooks/kaggle_training.ipynb` on Kaggle (with GPU accelerator enabled: T4 x2 or P100).
- Or run locally if dedicated CUDA GPU is available:
```bash
python training/scripts/train.py --config training/configs/baseline.yaml
```

### Step 5: Evaluate on Held-Out Test Split
Calibrates the operating threshold on the validation split and computes EER on the test split:
```bash
python training/scripts/evaluate.py \
    --checkpoint training/checkpoints/best_model.pt \
    --manifest-csv training/data/metadata/metadata.csv \
    --val-split val \
    --test-split test \
    --output-json training/reports/test_evaluation.json
```

### Step 6: Export Checkpoint to V-SHIELD Runtime
```bash
python training/scripts/export_model.py \
    --checkpoint training/checkpoints/best_model.pt \
    --metrics-json training/reports/test_evaluation.json \
    --output-dir models/vshield_antispoof_v1 \
    --status TRAINED
```

The exported model and `model_meta.json` are immediately recognized by the V-SHIELD FastAPI backend without restarting configuration.
