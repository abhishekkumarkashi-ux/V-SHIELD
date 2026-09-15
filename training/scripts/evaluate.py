#!/usr/bin/env python3
"""
Scientific Evaluation Script for V-SHIELD Anti-Spoofing Checkpoints.
Calibrates optimal decision threshold on Validation set, then evaluates on held-out Test set.
Reports EER, ROC-AUC, Precision, Recall, F1, and Confusion Matrix without data leakage.
"""

import os
import sys
import json
import argparse
import yaml
import numpy as np
import torch

# Add repo root and ml/src to path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ml_src = os.path.join(repo_root, "ml", "src")
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
if ml_src not in sys.path:
    sys.path.insert(0, ml_src)

from model import LightweightAntiSpoofCNN
from training.datasets.torch_dataset import create_dataloader
from training.metrics import compute_eer, compute_classification_metrics, compute_far_frr

def evaluate_loader(model: torch.nn.Module, loader, device: torch.device):
    model.eval()
    all_probs = []
    all_targets = []

    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            logits = model(x)
            probs = torch.sigmoid(logits).cpu().numpy().flatten()
            all_probs.extend(probs)
            all_targets.extend(y.numpy().flatten())

    return np.array(all_targets), np.array(all_probs)

def run_evaluation(
    checkpoint_path: str,
    manifest_csv: str,
    val_split: str = "val",
    test_split: str = "test",
    config_path: str = "training/configs/baseline.yaml",
    device_str: str = "auto",
    output_json: str = None
):
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    if not os.path.exists(manifest_csv):
        raise FileNotFoundError(f"Manifest CSV not found: {manifest_csv}")

    device = torch.device("cuda" if device_str == "cuda" or (device_str == "auto" and torch.cuda.is_available()) else "cpu")
    print(f"[*] Evaluating on device: {device}")

    # Load config
    cfg = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

    # Load model (handles both full training checkpoint and pure weights)
    print(f"[*] Loading model checkpoint from: {checkpoint_path}")
    model = LightweightAntiSpoofCNN(config=cfg).to(device)
    raw_ckpt = torch.load(checkpoint_path, map_location=device, weights_only=True)
    if isinstance(raw_ckpt, dict) and "model_state_dict" in raw_ckpt:
        state_dict = raw_ckpt["model_state_dict"]
    else:
        state_dict = raw_ckpt

    model.load_state_dict(state_dict)
    model.eval()

    # 1. Calibrate threshold on Validation split
    calibrated_threshold = 0.5
    val_eer = None
    try:
        print(f"[*] Calibrating threshold on '{val_split}' split...")
        val_loader = create_dataloader(manifest_csv, split=val_split, batch_size=16, shuffle=False, mode="eval")
        if len(val_loader.dataset) > 0:
            val_targets, val_probs = evaluate_loader(model, val_loader, device)
            val_eer, calibrated_threshold = compute_eer(val_targets, val_probs)
            print(f"    [+] Optimal Validation Threshold: {calibrated_threshold:.4f} (Validation EER = {val_eer * 100:.2f}%)")
    except Exception as e:
        print(f"    [!] Could not calibrate on validation split: {e}. Defaulting threshold to 0.5")

    # 2. Evaluate held-out Test split
    print(f"[*] Evaluating held-out '{test_split}' split...")
    test_loader = create_dataloader(manifest_csv, split=test_split, batch_size=16, shuffle=False, mode="eval")
    test_targets, test_probs = evaluate_loader(model, test_loader, device)

    metrics = compute_classification_metrics(test_targets, test_probs, threshold=calibrated_threshold)
    test_far, test_frr = compute_far_frr(test_targets, test_probs, calibrated_threshold)

    report_text = f"""=======================================================
          V-SHIELD TEST EVALUATION REPORT
=======================================================
Checkpoint:                {checkpoint_path}
Manifest:                  {manifest_csv}
Total Test Samples:        {len(test_targets)}
Bonafide Samples:          {int(np.sum(test_targets == 0))}
Spoof Samples:             {int(np.sum(test_targets == 1))}
-------------------------------------------------------
Operating Threshold:       {calibrated_threshold:.4f} (Calibrated on {val_split})
Calibration Method:        Validation EER Minimization (FAR == FRR)
Validation EER:            {f"{val_eer * 100:.2f}%" if val_eer is not None else "N/A"}
-------------------------------------------------------
TEST SET PERFORMANCE (UNBIASED HELD-OUT):
Test EER:                  {metrics['eer'] * 100:.2f}%
Test ROC-AUC:              {metrics['roc_auc']:.4f}
Test Accuracy:             {metrics['accuracy'] * 100:.2f}%
Test Precision:            {metrics['precision'] * 100:.2f}%
Test Recall:               {metrics['recall'] * 100:.2f}%
Test F1 Score:             {metrics['f1']:.4f}
False Alarm Rate (FAR):    {test_far * 100:.2f}%
False Rejection Rate (FRR):{test_frr * 100:.2f}%
-------------------------------------------------------
Confusion Matrix:
  True Negative (Bonafide): {metrics['tn']} | False Positive (Spoof):    {metrics['fp']}
  False Negative (Bonafide):{metrics['fn']} | True Positive (Spoof):     {metrics['tp']}
=======================================================
"""
    print("\n" + report_text)

    report_payload = {
        "checkpoint": checkpoint_path,
        "manifest": manifest_csv,
        "calibration_method": "Validation EER Minimization (FAR == FRR)",
        "validation_split": val_split,
        "validation_eer": val_eer,
        "operating_threshold": calibrated_threshold,
        "test_split": test_split,
        "total_test_samples": len(test_targets),
        "test_metrics": metrics,
        "test_far": test_far,
        "test_frr": test_frr
    }

    if output_json:
        if not os.path.isabs(output_json):
            output_json = os.path.join(repo_root, output_json)
        os.makedirs(os.path.dirname(os.path.abspath(output_json)), exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as jf:
            json.dump(report_payload, jf, indent=2)
        print(f"[+] Machine-readable evaluation JSON saved: {output_json}")

        # Also save human-readable text report alongside
        text_report_path = os.path.splitext(output_json)[0] + ".txt"
        with open(text_report_path, "w", encoding="utf-8") as tf:
            tf.write(report_text)
        print(f"[+] Human-readable evaluation text report saved: {text_report_path}")

    return report_payload

def main():
    parser = argparse.ArgumentParser(description="Evaluate V-SHIELD anti-spoof model.")
    parser.add_argument("--checkpoint", default="training/checkpoints/best_model.pt", help="Path to model checkpoint (.pt)")
    parser.add_argument("--manifest-csv", default="training/data/metadata/metadata.csv", help="Path to manifest CSV")
    parser.add_argument("--val-split", default="val", help="Split used to calibrate threshold")
    parser.add_argument("--test-split", default="test", help="Split to evaluate")
    parser.add_argument("--config", default="training/configs/baseline.yaml", help="Path to config YAML")
    parser.add_argument("--device", default="auto", help="Device ('cpu', 'cuda', 'auto')")
    parser.add_argument("--output-json", default="reports/phase_2b_evaluation.json", help="Save evaluation report as JSON")

    args = parser.parse_args()
    run_evaluation(
        checkpoint_path=args.checkpoint,
        manifest_csv=args.manifest_csv,
        val_split=args.val_split,
        test_split=args.test_split,
        config_path=args.config,
        device_str=args.device,
        output_json=args.output_json
    )

if __name__ == "__main__":
    main()
