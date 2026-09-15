"""
Comprehensive Test Suite for V-SHIELD Anti-Spoof Training Pipeline.
Tests dataset adapters, audio preprocessing, window extraction, speaker disjointness,
PyTorch dataset/dataloader, model forward/backward passes, metrics, checkpoint export,
and inference compatibility.
All tests execute fast on CPU without requiring the full ASVspoof dataset.
"""

import os
import sys
import json
import tempfile
import csv
import numpy as np
import soundfile as sf
import torch
import torch.nn as nn
import pytest

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

ml_src = os.path.join(REPO_ROOT, "ml", "src")
if ml_src not in sys.path:
    sys.path.insert(0, ml_src)

from training.datasets.base import AudioSampleRecord
from training.datasets.torch_dataset import AntiSpoofDataset, create_dataloader
from training.audio.loader import load_audio, TARGET_SAMPLE_RATE
from training.audio.preprocessing import (
    sanitize_waveform,
    normalize_peak_amplitude,
    pad_or_crop_waveform,
    preprocess_audio,
    WINDOW_SAMPLES
)
from training.audio.windowing import extract_sliding_windows, HOP_SAMPLES
from training.scripts.split_dataset import verify_speaker_disjointness, split_by_speaker
from training.scripts.validate_dataset import validate_dataset
from training.scripts.export_model import validate_checkpoint_weights, export_model
from training.metrics.eer import (
    compute_far_frr,
    compute_eer,
    compute_roc_auc,
    compute_classification_metrics
)
from model import LightweightAntiSpoofCNN
from backend.app.ml.model import model_instance


# ---------------------------------------------------------------------------
# 1. Dataset Manifest Parsing & Record Schema
# ---------------------------------------------------------------------------
def test_audio_sample_record_schema():
    record = AudioSampleRecord(
        file_path="/tmp/test_bonafide.flac",
        speaker_id="LA_0001",
        label=0,
        label_name="bonafide",
        attack_type="bonafide",
        dataset="ASVspoof2019_LA",
        split="train",
        sample_rate=16000,
        duration_seconds=4.0,
        num_samples=64000
    )
    d = record.to_dict()
    assert d["label"] == 0
    assert d["label_name"] == "bonafide"
    assert d["speaker_id"] == "LA_0001"
    assert d["sample_rate"] == 16000
    assert d["num_samples"] == 64000


def test_manifest_csv_parsing(tmp_path):
    csv_file = tmp_path / "test_manifest.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "file_path", "speaker_id", "label", "label_name", "attack_type", "dataset", "split", "sample_rate", "duration_seconds", "num_samples"
        ])
        writer.writeheader()
        writer.writerow({
            "file_path": str(tmp_path / "f1.flac"),
            "speaker_id": "SPK_01",
            "label": "0",
            "label_name": "bonafide",
            "attack_type": "bonafide",
            "dataset": "ASVspoof2019_LA",
            "split": "train",
            "sample_rate": "16000",
            "duration_seconds": "4.0",
            "num_samples": "64000"
        })
        writer.writerow({
            "file_path": str(tmp_path / "f2.flac"),
            "speaker_id": "SPK_02",
            "label": "1",
            "label_name": "spoof",
            "attack_type": "A01",
            "dataset": "ASVspoof2019_LA",
            "split": "val",
            "sample_rate": "16000",
            "duration_seconds": "3.5",
            "num_samples": "56000"
        })

    train_ds = AntiSpoofDataset(manifest_csv=str(csv_file), split="train")
    assert len(train_ds) == 1
    assert train_ds.records[0]["label"] == 0
    assert train_ds.records[0]["speaker_id"] == "SPK_01"

    val_ds = AntiSpoofDataset(manifest_csv=str(csv_file), split="val")
    assert len(val_ds) == 1
    assert val_ds.records[0]["label"] == 1
    assert val_ds.records[0]["speaker_id"] == "SPK_02"


# ---------------------------------------------------------------------------
# 2 & 3 & 4. Invalid Audio, NaN & Inf Detection
# ---------------------------------------------------------------------------
def test_sanitize_waveform_nans_and_infs():
    tensor = torch.tensor([[0.5, float('nan'), -0.2, float('inf'), float('-inf')]])
    sanitized = sanitize_waveform(tensor)
    assert not torch.isnan(sanitized).any(), "NaNs must be replaced"
    assert not torch.isinf(sanitized).any(), "Infs must be replaced"
    assert sanitized[0, 1].item() == 0.0
    assert sanitized[0, 3].item() == 0.0
    assert sanitized[0, 4].item() == 0.0


def test_validate_checkpoint_weights():
    clean_dict = {"fc.weight": torch.tensor([[0.1, -0.5], [0.3, 0.4]])}
    assert validate_checkpoint_weights(clean_dict) is True

    nan_dict = {"fc.weight": torch.tensor([[0.1, float('nan')], [0.3, 0.4]])}
    assert validate_checkpoint_weights(nan_dict) is False

    inf_dict = {"fc.weight": torch.tensor([[0.1, -0.5], [float('inf'), 0.4]])}
    assert validate_checkpoint_weights(inf_dict) is False


def test_dataset_validator_catches_invalid_and_corrupt(tmp_path):
    # 1. Create a corrupt audio file
    corrupt_audio = tmp_path / "corrupt.wav"
    corrupt_audio.write_bytes(b"NOT_A_VALID_RIFF_HEADER")

    # 2. Create a zero-length audio file
    zero_audio = tmp_path / "zero.wav"
    zero_audio.write_bytes(b"")

    manifest = tmp_path / "manifest.csv"
    with open(manifest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file_path", "speaker_id", "label", "split"])
        writer.writeheader()
        writer.writerow({"file_path": str(tmp_path / "non_existent.wav"), "speaker_id": "SPK1", "label": "0", "split": "train"})
        writer.writerow({"file_path": str(corrupt_audio), "speaker_id": "SPK2", "label": "1", "split": "train"})
        writer.writerow({"file_path": str(zero_audio), "speaker_id": "SPK3", "label": "0", "split": "train"})

    report = validate_dataset(str(manifest), check_audio_content=True)
    assert report["status"] == "FAIL"
    assert report["missing_files"] >= 1
    assert (report["corrupt_files"] >= 1 or len(report["corrupt_files"]) + len(report.get("zero_length_files", [])) >= 1)


# ---------------------------------------------------------------------------
# 5 & 6. Sample-rate and Mono Conversion
# ---------------------------------------------------------------------------
def test_audio_loader_resampling_and_mono(tmp_path):
    # Create stereo 48kHz test file
    sr_48k = 48000
    duration_s = 1.0
    num_samples_48k = int(sr_48k * duration_s)
    stereo_data = np.random.uniform(-0.5, 0.5, (num_samples_48k, 2)).astype(np.float32)
    
    file_48k = str(tmp_path / "stereo_48k.wav")
    sf.write(file_48k, stereo_data, sr_48k)

    # Load using V-SHIELD loader
    waveform, sr = load_audio(file_48k, target_sr=TARGET_SAMPLE_RATE)

    assert sr == 16000, f"Expected 16000 Hz target, got {sr}"
    assert waveform.dim() == 2, "Waveform should be 2D tensor (channels, time)"
    assert waveform.shape[0] == 1, f"Expected mono (1 channel), got {waveform.shape[0]}"
    # Expected samples approximately 16000
    assert abs(waveform.shape[1] - 16000) <= 50, f"Expected ~16000 samples, got {waveform.shape[1]}"


# ---------------------------------------------------------------------------
# 7. Window Generation & Padding
# ---------------------------------------------------------------------------
def test_pad_or_crop_short_audio():
    short_audio = torch.randn(1, 16000)  # 1.0s
    padded = pad_or_crop_waveform(short_audio, target_length=64000, mode="deterministic")
    assert padded.shape == (1, 64000)
    assert torch.equal(padded[:, :16000], short_audio)
    assert torch.all(padded[:, 16000:] == 0.0)


def test_pad_or_crop_long_audio():
    long_audio = torch.randn(1, 100000)
    cropped = pad_or_crop_waveform(long_audio, target_length=64000, mode="deterministic")
    assert cropped.shape == (1, 64000)
    assert torch.equal(cropped, long_audio[:, :64000])


def test_extract_sliding_windows():
    # 6.0 seconds of audio = 96,000 samples
    continuous_audio = torch.randn(1, 96000)
    windows = extract_sliding_windows(continuous_audio, window_samples=WINDOW_SAMPLES, hop_samples=HOP_SAMPLES)
    
    # Window 0: 0 to 64000
    # Window 1: 16000 to 80000
    # Window 2: 32000 to 96000
    # Window 3 (padded tail from 48000 to 96000): 48000 samples padded to 64000
    assert len(windows) == 4
    for w in windows:
        assert w.shape == (1, 64000)
        assert torch.all(torch.isfinite(w))
        # Peak amplitude normalized to <= 1.0
        assert torch.max(torch.abs(w)).item() <= 1.0001


# ---------------------------------------------------------------------------
# 8. Speaker Leakage Prevention
# ---------------------------------------------------------------------------
def test_speaker_disjointness_pass():
    records = [
        {"speaker_id": "SPK_A", "split": "train"},
        {"speaker_id": "SPK_B", "split": "train"},
        {"speaker_id": "SPK_C", "split": "val"},
        {"speaker_id": "SPK_D", "split": "test"},
    ]
    assert verify_speaker_disjointness(records) is True


def test_speaker_disjointness_catches_leakage():
    # SPK_A leaks into val
    records_tv_leak = [
        {"speaker_id": "SPK_A", "split": "train"},
        {"speaker_id": "SPK_A", "split": "val"},
        {"speaker_id": "SPK_C", "split": "test"},
    ]
    assert verify_speaker_disjointness(records_tv_leak) is False

    # SPK_B leaks into test
    records_tt_leak = [
        {"speaker_id": "SPK_B", "split": "train"},
        {"speaker_id": "SPK_C", "split": "val"},
        {"speaker_id": "SPK_B", "split": "test"},
    ]
    assert verify_speaker_disjointness(records_tt_leak) is False


def test_split_by_speaker(tmp_path):
    in_csv = tmp_path / "raw_manifest.csv"
    out_csv = tmp_path / "split_manifest.csv"

    speakers = [f"SPK_{i:02d}" for i in range(20)]
    records = []
    for spk in speakers:
        for j in range(3):
            records.append({
                "file_path": f"/data/{spk}_{j}.flac",
                "speaker_id": spk,
                "label": "0" if int(spk[-2:]) % 2 == 0 else "1",
                "split": "unassigned"
            })

    with open(in_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file_path", "speaker_id", "label", "split"])
        writer.writeheader()
        writer.writerows(records)

    split_by_speaker(str(in_csv), str(out_csv), train_ratio=0.70, val_ratio=0.15, test_ratio=0.15, seed=42)

    with open(out_csv, "r", encoding="utf-8") as f:
        split_records = list(csv.DictReader(f))

    assert len(split_records) == 60
    assert verify_speaker_disjointness(split_records) is True


# ---------------------------------------------------------------------------
# 9. Label Mapping Convention
# ---------------------------------------------------------------------------
def test_label_mapping_convention():
    bonafide_record = AudioSampleRecord(
        file_path="dummy.flac", speaker_id="S1", label=0, label_name="bonafide",
        attack_type="bonafide", dataset="ASVspoof", split="train"
    )
    spoof_record = AudioSampleRecord(
        file_path="dummy_spoof.flac", speaker_id="S2", label=1, label_name="spoof",
        attack_type="A01", dataset="ASVspoof", split="train"
    )
    assert bonafide_record.label == 0, "Bonafide must be 0"
    assert spoof_record.label == 1, "Spoof must be 1"


# ---------------------------------------------------------------------------
# 10 & 11. Model Forward Pass & Loss Backward Pass
# ---------------------------------------------------------------------------
def test_model_forward_and_backward():
    model = LightweightAntiSpoofCNN()
    model.train()

    # Batch of 2 audio windows of 64,000 samples each
    batch_audio = torch.randn(2, 1, 64000)
    targets = torch.tensor([[0.0], [1.0]], dtype=torch.float32)

    logits = model(batch_audio)
    assert logits.shape == (2, 1), f"Expected (2, 1), got {logits.shape}"
    assert torch.all(torch.isfinite(logits)), "Logits must be finite"

    criterion = nn.BCEWithLogitsLoss()
    loss = criterion(logits, targets)
    assert loss.item() > 0.0
    assert torch.isfinite(loss)

    loss.backward()
    # Verify gradients exist and are finite
    for name, param in model.named_parameters():
        if param.requires_grad:
            assert param.grad is not None, f"Gradient missing for {name}"
            assert torch.all(torch.isfinite(param.grad)), f"Non-finite gradient in {name}"


# ---------------------------------------------------------------------------
# 12. Checkpoint Save and Reload
# ---------------------------------------------------------------------------
def test_checkpoint_save_and_reload(tmp_path):
    model = LightweightAntiSpoofCNN()
    ckpt_path = tmp_path / "test_model.pt"
    torch.save(model.state_dict(), str(ckpt_path))

    state_dict = torch.load(str(ckpt_path), map_location="cpu", weights_only=True)
    assert validate_checkpoint_weights(state_dict) is True

    model.eval()
    model_reloaded = LightweightAntiSpoofCNN()
    model_reloaded.load_state_dict(state_dict)
    model_reloaded.eval()

    test_input = torch.randn(1, 1, 64000)
    with torch.no_grad():
        out1 = model(test_input)
        out2 = model_reloaded(test_input)

    assert torch.allclose(out1, out2, atol=1e-6), "Reloaded model must produce identical outputs"


# ---------------------------------------------------------------------------
# 13. Model Export and Metadata Generation
# ---------------------------------------------------------------------------
def test_export_model_and_metadata(tmp_path):
    source_model = LightweightAntiSpoofCNN()
    source_ckpt = tmp_path / "source.pt"
    torch.save(source_model.state_dict(), str(source_ckpt))

    export_dir = tmp_path / "exported_vshield_v1"
    export_model(
        checkpoint_path=str(source_ckpt),
        output_dir=str(export_dir),
        dataset_name="ASVspoof2019_LA_Test",
        threshold=0.5234,
        status="TRAINED",
        validation_status="RESEARCH_VALIDATED"
    )

    exported_pt = export_dir / "best_model.pt"
    metadata_json = export_dir / "model_meta.json"

    assert exported_pt.exists(), "best_model.pt must be created"
    assert metadata_json.exists(), "model_meta.json must be created"

    with open(metadata_json, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["model_name"] == "vshield_antispoof_v1"
    assert meta["architecture"] == "LightweightAntiSpoofCNN"
    assert meta["status"] == "TRAINED"
    assert meta["production_ready"] is False
    assert meta["validation_status"] == "RESEARCH_VALIDATED"
    assert meta["sample_rate"] == 16000
    assert meta["window_samples"] == 64000
    assert meta["threshold"] == 0.5234


# ---------------------------------------------------------------------------
# 14. Training Preprocessing & Backend Inference Compatibility
# ---------------------------------------------------------------------------
def test_inference_compatibility():
    # 1. Simulate 4.5 seconds of raw 16kHz audio
    raw_np = np.random.uniform(-0.8, 0.8, 72000).astype(np.float32)
    raw_tensor = torch.from_numpy(raw_np).unsqueeze(0)  # (1, 72000)

    # 2. Process with training preprocessing
    preprocessed_tensor = preprocess_audio(raw_tensor, target_length=64000, mode="deterministic")
    assert preprocessed_tensor.shape == (1, 64000)

    # 3. Process identical numpy audio with backend model_instance
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    model_path = os.path.join(base_dir, "models", "vshield_antispoof_v1", "best_model.pt")
    model_instance.load_model(model_path)
    assert model_instance.is_loaded is True

    # Pass preprocessed numpy window
    result = model_instance.predict_pcm(preprocessed_tensor.squeeze(0).numpy())
    assert "spoof_probability" in result
    prob = result["spoof_probability"]
    assert 0.0 <= prob <= 1.0


# ---------------------------------------------------------------------------
# 15. Threshold and Metric Calculations (EER, FAR, FRR, ROC-AUC)
# ---------------------------------------------------------------------------
def test_metrics_calculation():
    # Perfectly separable synthetic scores
    # 5 bonafide (label 0) with low scores [0.1, 0.15, 0.2, 0.25, 0.3]
    # 5 spoof (label 1) with high scores [0.7, 0.75, 0.8, 0.85, 0.9]
    labels = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    scores = np.array([0.1, 0.15, 0.2, 0.25, 0.3, 0.7, 0.75, 0.8, 0.85, 0.9])

    far, frr = compute_far_frr(labels, scores, threshold=0.5)
    assert far == 0.0
    assert frr == 0.0

    eer, opt_th = compute_eer(labels, scores)
    assert eer == 0.0
    assert 0.3 <= opt_th <= 0.7

    roc_auc = compute_roc_auc(labels, scores)
    assert roc_auc == 1.0

    metrics = compute_classification_metrics(labels, scores, threshold=0.5)
    assert metrics["accuracy"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["tp"] == 5
    assert metrics["tn"] == 5
    assert metrics["fp"] == 0
    assert metrics["fn"] == 0


# ---------------------------------------------------------------------------
# 16. Phase 2B: Dataset Discovery & Protocol Parsing
# ---------------------------------------------------------------------------
def test_dataset_discovery_and_strict_error(tmp_path):
    from training.scripts.build_manifest import build_manifest

    # Test 1: Missing protocol raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        build_manifest(
            dataset_name="ASVspoof2019_LA",
            dataset_root=str(tmp_path / "non_existent_dir"),
            output_csv=str(tmp_path / "manifest.csv"),
            splits=["train"]
        )

    # Test 2: Valid mock dataset structure
    ds_root = tmp_path / "mock_asvspoof"
    proto_dir = ds_root / "ASVspoof2019_LA_cm_protocols"
    audio_dir = ds_root / "ASVspoof2019_LA_train" / "flac"
    proto_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    proto_file = proto_dir / "ASVspoof2019.LA.cm.train.trn.txt"
    with open(proto_file, "w", encoding="utf-8") as f:
        f.write("LA_0001 LA_T_0000001 - - bonafide\n")
        f.write("LA_0002 LA_T_0000002 - A01 spoof\n")

    # Create dummy audio files
    sf.write(str(audio_dir / "LA_T_0000001.flac"), np.zeros(16000, dtype=np.float32), 16000)
    sf.write(str(audio_dir / "LA_T_0000002.flac"), np.zeros(16000, dtype=np.float32), 16000)

    out_csv = tmp_path / "discovered_manifest.csv"
    build_manifest(
        dataset_name="asvspoof2019",
        dataset_root=str(ds_root),
        output_csv=str(out_csv),
        splits=["train"]
    )

    assert out_csv.exists()
    with open(out_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["label"] == "0"
    assert rows[0]["label_name"] == "bonafide"
    assert rows[1]["label"] == "1"
    assert rows[1]["attack_type"] == "A01"


# ---------------------------------------------------------------------------
# 17. Phase 2B: Resume Training & Checkpoint Payload
# ---------------------------------------------------------------------------
def test_resume_checkpoint_payload(tmp_path):
    model = LightweightAntiSpoofCNN()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    ckpt_file = tmp_path / "resume_ckpt.pt"
    payload = {
        "epoch": 7,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "best_val_eer": 0.082,
        "best_epoch": 5,
        "history": [{"epoch": 1, "val_eer": 0.15}, {"epoch": 5, "val_eer": 0.082}],
        "config": {"training": {"seed": 42}},
        "seed": 42
    }
    torch.save(payload, str(ckpt_file))

    loaded = torch.load(str(ckpt_file), map_location="cpu", weights_only=False)
    assert loaded["epoch"] == 7
    assert loaded["best_val_eer"] == 0.082
    assert "model_state_dict" in loaded
    assert "optimizer_state_dict" in loaded

    # Verify model reload from dict
    model2 = LightweightAntiSpoofCNN()
    model2.load_state_dict(loaded["model_state_dict"])
    model.eval()
    model2.eval()
    test_x = torch.randn(1, 1, 64000)
    with torch.no_grad():
        out1 = model(test_x)
        out2 = model2(test_x)
    assert torch.allclose(out1, out2, atol=1e-6)


# ---------------------------------------------------------------------------
# 18. Phase 2B: Dual Evaluation Reporting (JSON + Text)
# ---------------------------------------------------------------------------
def test_evaluation_dual_reporting(tmp_path):
    from training.scripts.evaluate import run_evaluation

    # Create dummy checkpoint
    model = LightweightAntiSpoofCNN()
    ckpt_path = tmp_path / "eval_model.pt"
    torch.save(model.state_dict(), str(ckpt_path))

    # Create synthetic test audio
    audio_file = tmp_path / "eval_sample.wav"
    sf.write(str(audio_file), np.zeros(64000, dtype=np.float32), 16000)

    # Manifest with 1 val and 1 test sample
    manifest_csv = tmp_path / "eval_manifest.csv"
    with open(manifest_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file_path", "speaker_id", "label", "split"])
        writer.writeheader()
        writer.writerow({"file_path": str(audio_file), "speaker_id": "SPK1", "label": "0", "split": "val"})
        writer.writerow({"file_path": str(audio_file), "speaker_id": "SPK2", "label": "1", "split": "test"})

    out_json = tmp_path / "reports" / "phase_2b_evaluation.json"
    res = run_evaluation(
        checkpoint_path=str(ckpt_path),
        manifest_csv=str(manifest_csv),
        val_split="val",
        test_split="test",
        device_str="cpu",
        output_json=str(out_json)
    )

    assert out_json.exists(), "Machine-readable JSON report must be created"
    text_report = tmp_path / "reports" / "phase_2b_evaluation.txt"
    assert text_report.exists(), "Human-readable text report must be created"
    assert "operating_threshold" in res
    assert "test_metrics" in res

