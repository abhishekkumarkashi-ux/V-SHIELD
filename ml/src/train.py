import os
import time
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import numpy as np
import yaml
from pathlib import Path
from tqdm import tqdm
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix, roc_curve

from dataset import ASVSpoofDataset
from model import LightweightAntiSpoofCNN

def load_config():
    with open("ml/config.yaml", "r") as f:
        return yaml.safe_load(f)

def print_gpu_stats():
    print("=" * 50)
    print("GPU VERIFICATION")
    print("=" * 50)
    print(f"PyTorch version: {torch.__version__}")
    if torch.cuda.is_available():
        print(f"CUDA version: {torch.version.cuda}")
        print("CUDA available: True")
        print(f"GPU name: {torch.cuda.get_device_name(0)}")
        total_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"GPU VRAM: {total_mem:.2f} GB")
    else:
        print("CUDA available: False")
        print("WARNING: Training on CPU")
    print("=" * 50)

def compute_eer(y_true, y_scores):
    fpr, tpr, thresholds = roc_curve(y_true, y_scores)
    fnr = 1 - tpr
    # EER is where FPR == FNR
    diffs = np.absolute((fnr - fpr))
    eer_idx = np.nanargmin(diffs)
    eer = fpr[eer_idx]
    eer_threshold = thresholds[eer_idx]
    return eer, eer_threshold

def calculate_metrics(y_true, y_scores):
    # Safeguard against NaNs causing crashes
    y_scores = np.nan_to_num(y_scores, nan=0.0, posinf=1.0, neginf=0.0)
    
    preds = (y_scores >= 0.5).astype(int)
    acc = accuracy_score(y_true, preds)
    prec = precision_score(y_true, preds, zero_division=0)
    rec = recall_score(y_true, preds, zero_division=0)
    f1 = f1_score(y_true, preds, zero_division=0)
    try:
        roc_auc = roc_auc_score(y_true, y_scores)
    except ValueError:
        roc_auc = 0.5
        
    cm = confusion_matrix(y_true, preds)
    if cm.shape == (2, 2):
        tn, fp, fn, tp = cm.ravel()
    else:
        tn, fp, fn, tp = 0, 0, 0, 0
        
    eer, eer_thresh = compute_eer(y_true, y_scores)
    
    return acc, prec, rec, f1, roc_auc, tn, fp, fn, tp, cm, eer

def train():
    print_gpu_stats()
    
    config = load_config()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = torch.cuda.is_available()
    scaler = torch.amp.GradScaler(enabled=use_amp)
    
    metadata_path = os.path.join(config['dataset']['metadata_dir'], "asvspoof_metadata.csv")
    
    # 2. VERIFY ASVSPOOF LABELS
    print("=" * 50)
    print("VERIFY ASVSPOOF LABELS")
    print("=" * 50)
    print("0.0 = bonafide\n1.0 = spoof")
    print("Using exact balanced counts from config.")
    
    train_dataset = ASVSpoofDataset(metadata_path, partition="train", config=config)
    val_dataset = ASVSpoofDataset(metadata_path, partition="dev", config=config)
    
    # Check actual loaded counts
    t_bonafide = sum(1 for _, l in train_dataset if l.item() == 0.0)
    t_spoof = len(train_dataset) - t_bonafide
    v_bonafide = sum(1 for _, l in val_dataset if l.item() == 0.0)
    v_spoof = len(val_dataset) - v_bonafide
    
    print(f"\nDataset: ASVspoof 2019 (LA)")
    print(f"Train Dataset: {len(train_dataset)} (Bonafide: {t_bonafide}, Spoof: {t_spoof})")
    print(f"Validation Dataset: {len(val_dataset)} (Bonafide: {v_bonafide}, Spoof: {v_spoof})")
    
    train_loader = DataLoader(
        train_dataset, 
        batch_size=config['training']['batch_size'], 
        shuffle=True, 
        num_workers=config['training']['num_workers'],
        pin_memory=torch.cuda.is_available()
    )
    val_loader = DataLoader(
        val_dataset, 
        batch_size=config['training']['batch_size'], 
        shuffle=False, 
        num_workers=config['training']['num_workers'],
        pin_memory=torch.cuda.is_available()
    )
    
    model = LightweightAntiSpoofCNN(config).to(device)
    
    # Balanced Dataset -> NO POS_WEIGHT NEEDED for clean baseline
    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.AdamW(
        model.parameters(), 
        lr=config['training']['learning_rate'], 
        weight_decay=config['training']['weight_decay']
    )
    
    epochs = config['training']['epochs']
    patience = config['training']['early_stopping_patience']
    best_val_auc = 0.0
    epochs_no_improve = 0
    
    os.makedirs("models/vshield_antispoof_v1", exist_ok=True)
    
    print("=" * 50)
    print(f"STARTING TRAINING")
    print(f"Epochs: {epochs}")
    print(f"Batch size: {config['training']['batch_size']}")
    print(f"Learning rate: {config['training']['learning_rate']}")
    print("=" * 50)
    
    total_start_time = time.time()
    
    for epoch in range(epochs):
        epoch_start = time.time()
        
        # --- TRAIN ---
        model.train()
        train_loss = 0.0
        train_scores = []
        train_labels = []
        
        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs} [Train]")
        for waveforms, labels in pbar:
            waveforms = waveforms.to(device)
            labels = labels.to(device)
            
            optimizer.zero_grad()
            
            # Mixed Precision
            with torch.amp.autocast('cuda', enabled=use_amp):
                logits = model(waveforms)
                loss = criterion(logits, labels)
                
            scaler.scale(loss).backward()
            
            # Gradient clipping to prevent exploding gradients and NaNs
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            
            scaler.step(optimizer)
            scaler.update()
            
            train_loss += loss.item()
            probs = torch.sigmoid(logits).detach().cpu().numpy()
            train_scores.extend(probs.flatten())
            train_labels.extend(labels.cpu().numpy().flatten())
            
        train_loss /= len(train_loader)
        
        # --- VAL ---
        model.eval()
        val_loss = 0.0
        val_scores = []
        val_labels = []
        
        with torch.no_grad():
            for waveforms, labels in tqdm(val_loader, desc=f"Epoch {epoch+1}/{epochs} [Val]"):
                waveforms = waveforms.to(device)
                labels = labels.to(device)
                
                with torch.amp.autocast('cuda', enabled=use_amp):
                    logits = model(waveforms)
                    loss = criterion(logits, labels)
                    
                val_loss += loss.item()
                probs = torch.sigmoid(logits).cpu().numpy()
                val_scores.extend(probs.flatten())
                val_labels.extend(labels.cpu().numpy().flatten())
                
        val_loss /= len(val_loader)
        epoch_time = time.time() - epoch_start
        samples_per_sec = len(train_dataset) / epoch_time
        
        # Metrics
        tr_acc, tr_prec, tr_rec, tr_f1, tr_auc, _, _, _, _, _, _ = calculate_metrics(np.array(train_labels), np.array(train_scores))
        val_acc, val_prec, val_rec, val_f1, val_auc, tn, fp, fn, tp, cm, eer = calculate_metrics(np.array(val_labels), np.array(val_scores))
        
        # GPU Stats
        if torch.cuda.is_available():
            mem_alloc = torch.cuda.memory_allocated(0) / (1024**2)
            mem_res = torch.cuda.memory_reserved(0) / (1024**2)
            gpu_str = f"GPU Mem: {mem_alloc:.1f}MB alloc, {mem_res:.1f}MB res"
        else:
            gpu_str = "CPU Mode"
            
        print(f"\n[Epoch {epoch+1}] Time: {epoch_time:.1f}s | {samples_per_sec:.1f} samples/s | {gpu_str}")
        print(f"Train Loss: {train_loss:.4f} | Acc: {tr_acc:.4f} | AUC: {tr_auc:.4f}")
        print(f"Val Loss:   {val_loss:.4f} | Acc: {val_acc:.4f} | Precision: {val_prec:.4f} | Recall: {val_rec:.4f} | F1: {val_f1:.4f} | AUC: {val_auc:.4f}")
        print(f"Val Confusion: TN={tn}, FP={fp}, FN={fn}, TP={tp}")
        
        # Monitor ROC-AUC for saving
        if val_auc > best_val_auc:
            best_val_auc = val_auc
            epochs_no_improve = 0
            save_path = "models/vshield_antispoof_v1/best_model.pt"
            torch.save(model.state_dict(), save_path)
            print(f"Saved new best model with AUC: {val_auc:.4f}")
        else:
            epochs_no_improve += 1
            print(f"Early stopping counter: {epochs_no_improve}/{patience}")
            if epochs_no_improve >= patience:
                print("Early stopping triggered.")
                break

    # Final Output Report (as requested)
    print("\n" + "="*50)
    print("FINAL OUTPUT")
    print("="*50)
    print(f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}")
    print(f"CUDA: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB")
        
    print(f"\nDataset: ASVspoof 2019 LA")
    print(f"Train: {len(train_dataset)}")
    print(f"Validation: {len(val_dataset)}")
    print(f"Bonafide: {t_bonafide} (Train) + {v_bonafide} (Val)")
    print(f"Spoof: {t_spoof} (Train) + {v_spoof} (Val)")
    
    print(f"\nEpochs: {epoch+1}")
    print(f"Batch size: {config['training']['batch_size']}")
    print(f"Learning rate: {config['training']['learning_rate']}")
    total_time = time.time() - total_start_time
    print(f"Training time: {total_time/60:.1f} minutes")
    
    print(f"\nFinal Validation Metrics (Last Epoch):")
    print(f"Accuracy: {val_acc:.4f}")
    print(f"Precision: {val_prec:.4f}")
    print(f"Recall: {val_rec:.4f}")
    print(f"F1: {val_f1:.4f}")
    print(f"ROC-AUC: {val_auc:.4f}")
    print(f"EER: {eer:.4f}")
    
    print("\nConfusion Matrix:")
    print(cm)
    
    if torch.cuda.is_available():
        print(f"\nGPU memory usage: {torch.cuda.memory_allocated(0) / (1024**2):.1f} MB allocated")
        
    print("\nMODEL STATUS:")
    # Evaluate Success Criteria
    # 1. Meaningful AUC > 0.55
    # 2. Both classes predicted (TP>0, TN>0)
    if val_auc > 0.55 and tp > 0 and tn > 0:
        print("PASS")
        status = "PASS"
    else:
        print("FAIL (Model predicting single class or not learning)")
        status = "FAIL"
        
    import json
    
    # Save config
    with open("models/vshield_antispoof_v1/config.json", "w") as f:
        json.dump(config, f, indent=4)
        
    # Save metrics
    metrics = {
        "final_train_loss": train_loss,
        "final_val_loss": val_loss,
        "best_val_auc": best_val_auc,
        "accuracy": val_acc,
        "precision": val_prec,
        "recall": val_rec,
        "f1": val_f1,
        "eer": eer,
        "confusion_matrix": cm.tolist(),
        "training_time_minutes": total_time / 60.0,
        "gpu_used": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "both_classes_predicted": bool(tp > 0 and tn > 0),
        "status": status
    }
    with open("models/vshield_antispoof_v1/metrics.json", "w") as f:
        json.dump(metrics, f, indent=4)
        
    # Save dummy history (could track this properly, but saving final stats for now)
    history = {
        "epochs_completed": epoch + 1,
        "final_val_auc": val_auc
    }
    with open("models/vshield_antispoof_v1/training_history.json", "w") as f:
        json.dump(history, f, indent=4)
        
if __name__ == "__main__":
    train()
