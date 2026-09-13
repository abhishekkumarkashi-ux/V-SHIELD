import os
import sys
import torch
import numpy as np
import yaml
import soundfile as sf
from tqdm import tqdm
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, roc_curve, confusion_matrix

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dataset import ASVSpoofDataset
from model import LightweightAntiSpoofCNN
from robustness.noise_tests import add_white_noise
from robustness.volume_tests import change_volume
from robustness.resample_tests import simulate_resampling
from robustness.compression_tests import simulate_mu_law_compression, apply_bandpass_filter

def compute_eer(y_true, y_scores):
    if len(np.unique(y_true)) < 2:
        return 0.0, 0.5
    fpr, tpr, thresholds = roc_curve(y_true, y_scores)
    fnr = 1 - tpr
    eer_idx = np.nanargmin(np.absolute((fnr - fpr)))
    return fpr[eer_idx], thresholds[eer_idx]

def evaluate_subset(model, dataloader, device, transform_func=None, **kwargs):
    all_labels = []
    all_scores = []
    
    with torch.no_grad():
        # Evaluate up to 200 samples (batch_size=32 => ~6 batches) for speed
        max_batches = 6
        for i, (waveforms, labels) in enumerate(tqdm(dataloader, desc="Evaluating")):
            if i >= max_batches:
                break
                
            if transform_func is not None:
                transformed = []
                for w in waveforms:
                    np_audio = w.squeeze().numpy()
                    aug_np = transform_func(np_audio, **kwargs)
                    transformed.append(torch.tensor(aug_np, dtype=torch.float32).unsqueeze(0))
                waveforms = torch.stack(transformed)
                
            waveforms = waveforms.to(device)
            logits = model(waveforms)
            scores = torch.sigmoid(logits).cpu().numpy()
            
            all_scores.extend(scores.flatten())
            all_labels.extend(labels.numpy().flatten())
            
    all_labels = np.array(all_labels)
    all_scores = np.array(all_scores)
    preds = (all_scores >= 0.5).astype(int)
    
    acc = accuracy_score(all_labels, preds)
    f1 = f1_score(all_labels, preds, zero_division=0)
    roc_auc = roc_auc_score(all_labels, all_scores) if len(np.unique(all_labels)) > 1 else 0
    eer, eer_thresh = compute_eer(all_labels, all_scores)
    
    return {"acc": acc, "f1": f1, "auc": roc_auc, "eer": eer}

def run_tests():
    with open("ml/config.yaml", "r") as f:
        config = yaml.safe_load(f)
        
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Running robustness tests on {device}")
    
    # Load Model
    model = LightweightAntiSpoofCNN(config).to(device)
    model.load_state_dict(torch.load("models/vshield_antispoof_v1/model.pt", map_location=device, weights_only=True))
    model.eval()
    
    # Load Dataloader
    metadata_path = os.path.join(config['dataset']['metadata_dir'], "asvspoof_metadata.csv")
    dataset = ASVSpoofDataset(metadata_path, partition="dev", config=config)
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=config['training']['batch_size'], shuffle=True, num_workers=0)
    
    results = {}
    
    print("\n--- Baseline ---")
    results['Baseline'] = evaluate_subset(model, dataloader, device)
    print(results['Baseline'])
    
    print("\n--- Background Noise ---")
    results['Noise_20dB'] = evaluate_subset(model, dataloader, device, add_white_noise, snr_db=20)
    results['Noise_10dB'] = evaluate_subset(model, dataloader, device, add_white_noise, snr_db=10)
    results['Noise_0dB'] = evaluate_subset(model, dataloader, device, add_white_noise, snr_db=0)
    
    print("\n--- Volume Robustness ---")
    results['Vol_minus_6dB'] = evaluate_subset(model, dataloader, device, change_volume, db_change=-6.0)
    results['Vol_plus_6dB'] = evaluate_subset(model, dataloader, device, change_volume, db_change=6.0)
    
    print("\n--- Resampling ---")
    results['Resample_8kHz'] = evaluate_subset(model, dataloader, device, simulate_resampling, orig_sr=16000, target_sr=8000)
    
    print("\n--- Compression ---")
    results['MuLaw_Compression'] = evaluate_subset(model, dataloader, device, simulate_mu_law_compression)
    results['Bandpass_Filter'] = evaluate_subset(model, dataloader, device, apply_bandpass_filter, sr=16000)
    
    # Save Report
    with open("ml/reports/robustness/metrics.yaml", "w") as f:
        yaml.dump(results, f)
        
    print("\nRobustness metrics saved to ml/reports/robustness/metrics.yaml")

if __name__ == "__main__":
    run_tests()

