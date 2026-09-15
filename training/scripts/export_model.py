#!/usr/bin/env python3
"""
Model Checkpoint Exporter for V-SHIELD.
Validates model weights for NaNs/Infs, verifies architectural integrity,
and generates compliant model_meta.json metadata for backend runtime consumption.
"""

import os
import sys
import json
import shutil
import argparse
from datetime import datetime, timezone
import torch

# Add repo root and ml/src to path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ml_src = os.path.join(repo_root, "ml", "src")
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
if ml_src not in sys.path:
    sys.path.insert(0, ml_src)

from model import LightweightAntiSpoofCNN

def validate_checkpoint_weights(state_dict: dict) -> bool:
    """Verifies that no NaN or Inf weights exist in any layer."""
    for key, tensor in state_dict.items():
        if not torch.all(torch.isfinite(tensor)):
            print(f"[!] Invalid tensor in layer '{key}': contains NaN or Inf weights!")
            return False
    return True

import subprocess

def get_git_commit() -> str:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root).decode("utf-8").strip()
        return commit
    except Exception:
        return "UNKNOWN"

def export_model(
    checkpoint_path: str,
    output_dir: str = "models/vshield_antispoof_v1",
    metrics_json: str = None,
    dataset_name: str = "ASVspoof2019_LA",
    threshold: float = 0.5,
    status: str = "TRAINED",
    validation_status: str = "RESEARCH_VALIDATED",
    version: str = "1.0.0",
    training_device: str = "auto",
    random_seed: int = 42
):
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"Source checkpoint not found: {checkpoint_path}")

    if not os.path.isabs(output_dir):
        output_dir = os.path.join(repo_root, output_dir)
    os.makedirs(output_dir, exist_ok=True)

    print(f"[*] Validating source checkpoint: {checkpoint_path}")
    raw_ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if isinstance(raw_ckpt, dict) and "model_state_dict" in raw_ckpt:
        state_dict = raw_ckpt["model_state_dict"]
        if "config" in raw_ckpt and "training" in raw_ckpt["config"]:
            random_seed = raw_ckpt["config"]["training"].get("seed", random_seed)
    else:
        state_dict = raw_ckpt

    # 1. Weights integrity audit
    if not validate_checkpoint_weights(state_dict):
        raise ValueError("Checkpoint validation failed: Non-finite weights detected.")

    # 2. Architecture loading verification
    model = LightweightAntiSpoofCNN()
    try:
        model.load_state_dict(state_dict)
        model.eval()
        print("[+] Architecture matches LightweightAntiSpoofCNN perfectly.")
    except Exception as e:
        raise RuntimeError(f"State dict does not match model architecture: {e}")

    total_params = sum(p.numel() for p in model.parameters())

    # 3. Copy clean checkpoint to target directory
    target_checkpoint = os.path.join(output_dir, "best_model.pt")
    torch.save(state_dict, target_checkpoint)
    print(f"[+] Clean checkpoint exported to: {target_checkpoint}")

    # 4. Read metrics if available
    validation_metrics = {}
    test_metrics = {}
    if metrics_json and os.path.exists(metrics_json):
        try:
            with open(metrics_json, "r", encoding="utf-8") as jf:
                eval_data = json.load(jf)
                test_metrics = eval_data.get("test_metrics", {})
                threshold = eval_data.get("operating_threshold", threshold)
                val_eer = eval_data.get("validation_eer")
                if val_eer is not None:
                    validation_metrics["eer"] = val_eer
                if "validation_metrics" in eval_data:
                    validation_metrics.update(eval_data["validation_metrics"])
        except Exception as e:
            print(f"[!] Warning reading metrics JSON: {e}")

    git_commit = get_git_commit()

    # 5. Generate truthful model_meta.json per Section 15 specifications
    meta = {
        "model_name": "vshield_antispoof_v1",
        "version": version,
        "status": status,
        "production_ready": False,  # Strict security rule: require human/security review before production flag
        "validation_status": validation_status,
        "training_dataset": dataset_name,
        "dataset_version": "2019_LA",
        "training_date": datetime.now(timezone.utc).isoformat(),
        "sample_rate": 16000,
        "channels": 1,
        "window_size": 64000,
        "window_samples": 64000,
        "window_seconds": 4.0,
        "hop_size": 16000,
        "hop_seconds": 1.0,
        "input_format": "Float32 PCM (1, 64000)",
        "architecture": "LightweightAntiSpoofCNN",
        "parameter_count": total_params,
        "threshold": round(float(threshold), 4),
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "EER": test_metrics.get("eer", validation_metrics.get("eer", "N/A")),
        "ROC_AUC": test_metrics.get("roc_auc", "N/A"),
        "F1": test_metrics.get("f1", "N/A"),
        "training_device": training_device,
        "random_seed": random_seed,
        "git_commit": git_commit,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Model is research-trained and validated on benchmark datasets. Continuous real-world monitoring is recommended."
    }

    meta_path = os.path.join(output_dir, "model_meta.json")
    with open(meta_path, "w", encoding="utf-8") as mf:
        json.dump(meta, mf, indent=2)

    print(f"[+] Model metadata successfully generated at: {meta_path}")
    print(f"    Status: {status} | Production Ready: False | Validation Status: {validation_status}")
    print(f"    Parameters: {total_params:,} | Threshold: {threshold} | Git Commit: {git_commit[:8]}")

def main():
    parser = argparse.ArgumentParser(description="Export V-SHIELD anti-spoof model checkpoint with metadata.")
    parser.add_argument("--checkpoint", required=True, help="Path to trained checkpoint (.pt)")
    parser.add_argument("--output-dir", default="models/vshield_antispoof_v1", help="Target export folder")
    parser.add_argument("--metrics-json", default=None, help="Optional evaluation report JSON")
    parser.add_argument("--dataset-name", default="ASVspoof2019_LA", help="Dataset name")
    parser.add_argument("--threshold", type=float, default=0.5, help="Calibrated threshold")
    parser.add_argument("--status", default="TRAINED", help="Model status tag ('TRAINED', 'VALIDATED', 'RESEARCH_READY')")
    parser.add_argument("--validation-status", default="RESEARCH_VALIDATED", help="Validation status tag")
    parser.add_argument("--version", default="1.0.0", help="Model version string")

    args = parser.parse_args()
    export_model(
        checkpoint_path=args.checkpoint,
        output_dir=args.output_dir,
        metrics_json=args.metrics_json,
        dataset_name=args.dataset_name,
        threshold=args.threshold,
        status=args.status,
        validation_status=args.validation_status,
        version=args.version
    )

if __name__ == "__main__":
    main()
