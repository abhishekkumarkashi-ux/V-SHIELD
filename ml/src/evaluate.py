import os
import torch
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix, roc_curve
from torch.utils.data import DataLoader
import yaml
from tqdm import tqdm

from dataset import ASVSpoofDataset
from model import LightweightAntiSpoofCNN

def load_config():
    with open("ml/config.yaml", "r") as f:
        return yaml.safe_load(f)

def compute_eer(y_true, y_scores):
    """Calculates Equal Error Rate (EER)"""
    fpr, tpr, thresholds = roc_curve(y_true, y_scores)
    fnr = 1 - tpr
    
    # EER is where FPR == FNR
    eer_threshold = thresholds[np.nanargmin(np.absolute((fnr - fpr)))]
    eer = fpr[np.nanargmin(np.absolute((fnr - fpr)))]
    return eer, eer_threshold

def evaluate():
    config = load_config()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Evaluating on {device}")
    
    metadata_path = os.path.join(config['dataset']['metadata_dir'], "asvspoof_metadata.csv")
    
    # Evaluate on dev partition as evaluation labels might be masked
    dataset = ASVSpoofDataset(metadata_path, partition="dev", config=config)
    dataloader = DataLoader(dataset, batch_size=config['training']['batch_size'], shuffle=False, num_workers=0)
    
    model = LightweightAntiSpoofCNN(config).to(device)
    
    model_path = "models/vshield_antispoof_v1/model.pt"
    if not os.path.exists(model_path):
        print(f"ERROR: No trained model found at {model_path}. Run train.py first.")
        return
        
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    model.eval()
    
    all_labels = []
    all_scores = []
    
    print("Running inference on validation set...")
    with torch.no_grad():
        for waveforms, labels in tqdm(dataloader, desc="Evaluating"):
            waveforms = waveforms.to(device)
            logits = model(waveforms)
            scores = torch.sigmoid(logits).cpu().numpy()
            
            all_scores.extend(scores.flatten())
            all_labels.extend(labels.numpy().flatten())
            
    all_labels = np.array(all_labels)
    all_scores = np.array(all_scores)
    preds = (all_scores >= 0.5).astype(int)
    
    acc = accuracy_score(all_labels, preds)
    prec = precision_score(all_labels, preds, zero_division=0)
    rec = recall_score(all_labels, preds, zero_division=0)
    f1 = f1_score(all_labels, preds, zero_division=0)
    roc_auc = roc_auc_score(all_labels, all_scores)
    eer, eer_thresh = compute_eer(all_labels, all_scores)
    cm = confusion_matrix(all_labels, preds)
    
    print("\n=== V-SHIELD Model Evaluation Report ===")
    print(f"Accuracy:  {acc:.4f}")
    print(f"Precision: {prec:.4f}")
    print(f"Recall:    {rec:.4f}")
    print(f"F1-Score:  {f1:.4f}")
    print(f"ROC-AUC:   {roc_auc:.4f}")
    print(f"EER:       {eer:.4f} (at threshold {eer_thresh:.4f})")
    print("\nConfusion Matrix:")
    print(cm)
    
    # Save metrics
    os.makedirs("ml/logs", exist_ok=True)
    with open("ml/logs/evaluation_metrics.txt", "w") as f:
        f.write(f"Accuracy: {acc}\nPrecision: {prec}\nRecall: {rec}\nF1: {f1}\nROC_AUC: {roc_auc}\nEER: {eer}\n")
    print("\nMetrics saved to ml/logs/evaluation_metrics.txt")

if __name__ == "__main__":
    evaluate()
