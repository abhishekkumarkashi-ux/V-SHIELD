#!/usr/bin/env python3
"""
Training Script for V-SHIELD Anti-Spoofing Model.
Supports auto-device detection (CUDA/CPU), gradient clipping, EER validation,
checkpointing, and lightweight smoke testing without RAM exhaustion.
"""

import os
import sys
import yaml
import time
import json
import argparse
from datetime import datetime
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

# Add repo root and ml/src to path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ml_src = os.path.join(repo_root, "ml", "src")
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
if ml_src not in sys.path:
    sys.path.insert(0, ml_src)

from model import LightweightAntiSpoofCNN
from training.datasets.torch_dataset import create_dataloader
from training.metrics import compute_eer, compute_classification_metrics

def set_seed(seed: int = 42):
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)

def get_device(device_config: str = "auto") -> torch.device:
    if device_config == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    elif device_config == "cpu":
        return torch.device("cpu")
    else:
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")

def run_smoke_test(cfg: dict, device: torch.device):
    """
    Fast sanity check verifying model forward pass, loss computation,
    backward pass, optimizer step, validation, and checkpoint persistence
    using small synthetic deterministic batches.
    Does NOT claim detection accuracy.
    """
    print("\n" + "=" * 50)
    print("       STARTING SMOKE TEST SANITY CHECK")
    print("=" * 50)
    print(f"[*] Target Device: {device}")

    # Create tiny synthetic batch: 8 samples of 16kHz float32 audio (4.0s = 64,000 samples)
    set_seed(42)
    dummy_audio = torch.randn(8, 1, 64000)
    # Balanced labels: 4 bonafide (0), 4 spoof (1)
    dummy_labels = torch.tensor([[0.0], [1.0], [0.0], [1.0], [0.0], [1.0], [0.0], [1.0]])

    train_ds = TensorDataset(dummy_audio[:4], dummy_labels[:4])
    val_ds = TensorDataset(dummy_audio[4:], dummy_labels[4:])

    train_loader = DataLoader(train_ds, batch_size=2, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=2, shuffle=False)

    model = LightweightAntiSpoofCNN(config=cfg).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.BCEWithLogitsLoss()

    print("[*] Running forward & backward sanity step...")
    model.train()
    for batch_idx, (x, y) in enumerate(train_loader):
        x, y = x.to(device), y.to(device)
        optimizer.zero_grad()
        out = model(x)
        loss = criterion(out, y)
        loss.backward()
        optimizer.step()
        print(f"    Batch {batch_idx + 1}: Loss = {loss.item():.4f}")

    print("[*] Running validation sanity step...")
    model.eval()
    val_preds, val_targets = [], []
    with torch.no_grad():
        for x, y in val_loader:
            x = x.to(device)
            out = model(x)
            prob = torch.sigmoid(out).cpu().numpy()
            val_preds.extend(prob.flatten())
            val_targets.extend(y.numpy().flatten())

    eer, th = compute_eer(np.array(val_targets), np.array(val_preds))
    print(f"    Validation EER = {eer:.4f} at Threshold = {th:.4f}")

    # Checkpoint save & reload verification
    test_ckpt_dir = os.path.join(repo_root, "training", "checkpoints")
    os.makedirs(test_ckpt_dir, exist_ok=True)
    test_ckpt_path = os.path.join(test_ckpt_dir, "smoke_test_model.pt")

    torch.save(model.state_dict(), test_ckpt_path)
    print(f"[*] Checkpoint saved to: {test_ckpt_path}")

    # Reload checkpoint
    reloaded_model = LightweightAntiSpoofCNN(config=cfg).to(device)
    reloaded_model.load_state_dict(torch.load(test_ckpt_path, map_location=device, weights_only=True))
    reloaded_model.eval()

    # Compare output
    with torch.no_grad():
        out1 = model(dummy_audio[:1].to(device))
        out2 = reloaded_model(dummy_audio[:1].to(device))
        diff = torch.max(torch.abs(out1 - out2)).item()
        assert diff < 1e-5, f"Reloaded checkpoint output mismatch (diff={diff})"

    print(f"[+] Checkpoint reload verified successfully (max output diff = {diff:.8f}).")
    print("[+] SMOKE TEST PASSED: Training mechanics, backward pass, and checkpoint reload are 100% verified.")
    print("=" * 50 + "\n")

def train_model(cfg: dict, override_epochs: int = None, override_lr: float = None, override_batch_size: int = None, resume_checkpoint: str = None):
    seed = cfg.get("training", {}).get("seed", 42)
    set_seed(seed)

    device_pref = cfg.get("hardware", {}).get("device", "auto")
    device = get_device(device_pref)
    cuda_avail = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if cuda_avail else "N/A"

    print("\n" + "=" * 60)
    print("         V-SHIELD REAL ANTI-SPOOF MODEL TRAINING")
    print("=" * 60)
    print(f"[*] Execution Device:       {device}")
    print(f"[*] CUDA Available:         {cuda_avail}")
    print(f"[*] GPU Name:               {gpu_name}")
    if cuda_avail:
        print(f"[*] GPU Device Count:       {torch.cuda.device_count()}")
        print(f"[*] Current CUDA Device:    {torch.cuda.current_device()}")

    manifest_csv = cfg.get("dataset", {}).get("manifest_csv", "training/data/metadata/metadata.csv")
    if not os.path.isabs(manifest_csv):
        manifest_csv = os.path.join(repo_root, manifest_csv)

    if not os.path.exists(manifest_csv):
        print("\n" + "!" * 60)
        print(f"[!] Manifest not found at: {manifest_csv}")
        print("    V-SHIELD hardware protection active: Will not download 20GB datasets automatically.")
        print("    To train a real model:")
        print("    1. Download dataset (e.g., ASVspoof 2019 LA) and place in 'training/data/raw/'.")
        print("    2. Generate manifest:")
        print("       python training/scripts/build_manifest.py --dataset asvspoof2019 --root training/data/raw/ASVspoof2019_LA")
        print("    3. Validate dataset:")
        print("       python training/scripts/validate_dataset.py")
        print("    4. Rerun train.py --config training/configs/baseline.yaml")
        print("!" * 60 + "\n")
        return

    # Inspect manifest distribution
    import csv
    with open(manifest_csv, "r", encoding="utf-8") as f:
        records = list(csv.DictReader(f))

    total_samples = len(records)
    train_records = [r for r in records if "train" in (r.get("split") or "").lower()]
    val_records = [r for r in records if any(k in (r.get("split") or "").lower() for k in ("val", "dev"))]
    test_records = [r for r in records if any(k in (r.get("split") or "").lower() for k in ("test", "eval"))]

    train_bonafide = sum(1 for r in train_records if r.get("label") == "0")
    train_spoof = sum(1 for r in train_records if r.get("label") == "1")

    print("-" * 60)
    print("DATASET & SPLIT SUMMARY:")
    print(f"  Manifest CSV:             {manifest_csv}")
    print(f"  Total Samples:            {total_samples}")
    print(f"  Train Split Samples:      {len(train_records)}")
    print(f"    - Train Bonafide (0):   {train_bonafide}")
    print(f"    - Train Spoof (1):      {train_spoof}")
    print(f"  Validation Split Samples: {len(val_records)}")
    print(f"  Test Split Samples:       {len(test_records)}")

    # Hyperparameters
    t_cfg = cfg.get("training", {})
    batch_size = override_batch_size or t_cfg.get("batch_size", 16)
    epochs = override_epochs or t_cfg.get("epochs", 20)
    lr = override_lr or t_cfg.get("learning_rate", 0.0003)
    weight_decay = t_cfg.get("weight_decay", 0.0001)
    grad_clip = t_cfg.get("grad_clip", 5.0)
    num_workers = t_cfg.get("num_workers", 0)
    patience = t_cfg.get("early_stopping_patience", 5)

    # Class imbalance handling strategy
    pos_weight_cfg = t_cfg.get("pos_weight", "auto")
    if pos_weight_cfg == "auto" or t_cfg.get("auto_pos_weight", True):
        # In ASVspoof, spoof (1) often outnumbers bonafide (0) ~8:1
        # pos_weight adjusts loss for class 1: pos_weight = N_bonafide / N_spoof
        if train_spoof > 0 and train_bonafide > 0:
            pos_weight_val = float(train_bonafide / train_spoof)
        else:
            pos_weight_val = 1.0
        print(f"  Class Imbalance Strategy: AUTO-WEIGHTED BCE (pos_weight = {pos_weight_val:.4f})")
    else:
        pos_weight_val = float(pos_weight_cfg)
        print(f"  Class Imbalance Strategy: MANUAL BCE (pos_weight = {pos_weight_val:.4f})")

    # Instantiate Model & print architecture/parameter stats
    model = LightweightAntiSpoofCNN(config=cfg).to(device)
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    print("-" * 60)
    print("MODEL ARCHITECTURE & SPECIFICATIONS:")
    print(f"  Model Architecture:       LightweightAntiSpoofCNN")
    print(f"  Total Parameters:         {total_params:,}")
    print(f"  Trainable Parameters:     {trainable_params:,}")
    print(f"  Sample Rate:              16,000 Hz")
    print(f"  Input Window Size:        64,000 samples (4.0 seconds)")
    print(f"  Hop Size:                 16,000 samples (1.0 second)")
    print(f"  Batch Size:               {batch_size}")
    print(f"  Target Epochs:            {epochs}")
    print(f"  Learning Rate:            {lr}")
    print("=" * 60 + "\n")

    # DataLoaders
    train_loader = create_dataloader(
        manifest_csv=manifest_csv,
        split="train",
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        mode="train"
    )

    val_loader = create_dataloader(
        manifest_csv=manifest_csv,
        split="val",
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        mode="eval"
    )

    pos_weight = torch.tensor([pos_weight_val], device=device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=2)

    ckpt_dir = os.path.join(repo_root, cfg.get("output", {}).get("checkpoint_dir", "training/checkpoints"))
    report_dir = os.path.join(repo_root, cfg.get("output", {}).get("report_dir", "training/reports"))
    os.makedirs(ckpt_dir, exist_ok=True)
    os.makedirs(report_dir, exist_ok=True)

    start_epoch = 1
    best_val_eer = float("inf")
    best_epoch = -1
    no_improve_count = 0
    history = []

    # Resume support
    if resume_checkpoint:
        if not os.path.isabs(resume_checkpoint):
            resume_checkpoint = os.path.join(repo_root, resume_checkpoint)
        if os.path.exists(resume_checkpoint):
            print(f"[*] Resuming training from checkpoint: {resume_checkpoint}")
            ckpt_data = torch.load(resume_checkpoint, map_location=device)
            if isinstance(ckpt_data, dict) and "model_state_dict" in ckpt_data:
                model.load_state_dict(ckpt_data["model_state_dict"])
                if "optimizer_state_dict" in ckpt_data:
                    optimizer.load_state_dict(ckpt_data["optimizer_state_dict"])
                if "scheduler_state_dict" in ckpt_data and scheduler:
                    scheduler.load_state_dict(ckpt_data["scheduler_state_dict"])
                start_epoch = ckpt_data.get("epoch", 0) + 1
                best_val_eer = ckpt_data.get("best_val_eer", float("inf"))
                best_epoch = ckpt_data.get("best_epoch", -1)
                history = ckpt_data.get("history", [])
                print(f"[+] Resumed from epoch {start_epoch} | Best Val EER: {best_val_eer * 100:.2f}%")
            else:
                model.load_state_dict(ckpt_data)
                print("[+] Loaded model state dict weights. Starting training loop.")
        else:
            raise FileNotFoundError(f"Resume checkpoint not found: {resume_checkpoint}")

    print(f"\n[*] Starting training loop (epochs {start_epoch} to {epochs})...")
    start_time = time.time()

    for epoch in range(start_epoch, epochs + 1):
        epoch_start = time.time()
        model.train()
        train_loss = 0.0

        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            optimizer.step()
            train_loss += loss.item() * len(y)

        train_loss /= max(1, len(train_loader.dataset))

        # Validation
        model.eval()
        val_loss = 0.0
        val_probs, val_targets = [], []

        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                logits = model(x)
                loss = criterion(logits, y)
                val_loss += loss.item() * len(y)
                probs = torch.sigmoid(logits).cpu().numpy().flatten()
                val_probs.extend(probs)
                val_targets.extend(y.cpu().numpy().flatten())

        val_loss /= max(1, len(val_loader.dataset))
        val_metrics = compute_classification_metrics(np.array(val_targets), np.array(val_probs))
        val_eer = val_metrics["eer"]

        scheduler.step(val_loss)
        epoch_sec = time.time() - epoch_start

        print(f"Epoch {epoch:02d}/{epochs:02d} [{epoch_sec:.1f}s] | "
              f"Train Loss: {train_loss:.4f} | "
              f"Val Loss: {val_loss:.4f} | "
              f"Val EER: {val_eer * 100:.2f}% | "
              f"ROC-AUC: {val_metrics['roc_auc']:.4f}")

        # Checkpoint payloads
        full_ckpt_payload = {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict() if scheduler else None,
            "best_val_eer": best_val_eer,
            "best_epoch": best_epoch,
            "val_metrics": val_metrics,
            "config": cfg,
            "seed": seed,
            "history": history
        }

        # Save last checkpoint
        last_ckpt = os.path.join(ckpt_dir, "last_checkpoint.pt")
        last_model = os.path.join(ckpt_dir, "last_model.pt")
        torch.save(full_ckpt_payload, last_ckpt)
        torch.save(model.state_dict(), last_model)

        # Save best checkpoint
        if val_eer < best_val_eer:
            best_val_eer = val_eer
            best_epoch = epoch
            no_improve_count = 0
            best_ckpt = os.path.join(ckpt_dir, "best_checkpoint.pt")
            best_model = os.path.join(ckpt_dir, "best_model.pt")
            torch.save(full_ckpt_payload, best_ckpt)
            torch.save(model.state_dict(), best_model)
            print(f"    [+] New best model saved (Val EER: {best_val_eer * 100:.2f}%)")
        else:
            no_improve_count += 1
            if no_improve_count >= patience:
                print(f"[*] Early stopping triggered after {epoch} epochs (no improvement in {patience} epochs).")
                break

        history.append({
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "val_eer": val_eer,
            "val_roc_auc": val_metrics["roc_auc"],
            "val_accuracy": val_metrics["accuracy"]
        })

    total_time = time.time() - start_time
    print(f"\n[+] Training completed in {total_time / 60:.2f} minutes.")
    print(f"    Best Epoch: {best_epoch} (Val EER: {best_val_eer * 100:.2f}%)")

    # Save training report JSON
    report_file = os.path.join(report_dir, f"training_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "best_epoch": best_epoch,
            "best_val_eer": best_val_eer,
            "total_duration_sec": total_time,
            "device": str(device),
            "gpu_name": gpu_name,
            "parameter_count": total_params,
            "config": cfg,
            "history": history
        }, f, indent=2)
    print(f"    Report saved: {report_file}")

def main():
    parser = argparse.ArgumentParser(description="Train V-SHIELD anti-spoof model.")
    parser.add_argument("--config", default="training/configs/baseline.yaml", help="Path to training config YAML")
    parser.add_argument("--smoke-test", action="store_true", help="Run lightweight sanity test on small synthetic batches")
    parser.add_argument("--device", default=None, help="Device override ('cpu', 'cuda', 'auto')")
    parser.add_argument("--epochs", type=int, default=None, help="Override number of epochs")
    parser.add_argument("--batch-size", type=int, default=None, help="Override batch size")
    parser.add_argument("--lr", type=float, default=None, help="Override learning rate")
    parser.add_argument("--manifest", default=None, help="Override path to manifest CSV (supports env var VSHIELD_MANIFEST_PATH)")
    parser.add_argument("--resume", default=None, help="Resume training from an existing checkpoint (.pt)")

    args = parser.parse_args()

    cfg_path = args.config
    if not os.path.isabs(cfg_path):
        cfg_path = os.path.join(repo_root, cfg_path)

    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    # CLI / Environment Variable overrides
    device_override = args.device or os.environ.get("VSHIELD_DEVICE")
    if device_override:
        cfg.setdefault("hardware", {})["device"] = device_override

    manifest_override = args.manifest or os.environ.get("VSHIELD_MANIFEST_PATH")
    if manifest_override:
        cfg.setdefault("dataset", {})["manifest_csv"] = manifest_override

    device = get_device(cfg.get("hardware", {}).get("device", "auto"))

    if args.smoke_test:
        run_smoke_test(cfg, device)
    else:
        train_model(
            cfg, 
            override_epochs=args.epochs, 
            override_lr=args.lr,
            override_batch_size=args.batch_size,
            resume_checkpoint=args.resume
        )

if __name__ == "__main__":
    main()
