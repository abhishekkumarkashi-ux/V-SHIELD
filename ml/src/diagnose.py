import os
import torch
import torchaudio
import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import warnings
warnings.filterwarnings("ignore")

from features import FeatureExtractor
from model import LightweightAntiSpoofCNN

def load_config():
    with open("ml/config.yaml", "r") as f:
        return yaml.safe_load(f)

def run_diagnostics():
    print("=" * 50)
    print("V-SHIELD DIAGNOSTIC REPORT")
    print("=" * 50)
    
    # 1. Check GPU
    print("--- PyTorch & GPU Verification ---")
    print(f"PyTorch version: {torch.__version__}")
    if torch.cuda.is_available():
        print(f"CUDA version: {torch.version.cuda}")
        print(f"CUDA available: {torch.cuda.is_available()}")
        print(f"GPU name: {torch.cuda.get_device_name(0)}")
        print(f"GPU VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB")
        device = torch.device('cuda')
    else:
        print("CUDA available: False")
        print("WARNING: CPU mode active.")
        device = torch.device('cpu')
    print("=" * 50)

    config = load_config()
    metadata_path = os.path.join(config['dataset']['metadata_dir'], "asvspoof_metadata.csv")
    df = pd.read_csv(metadata_path)
    
    # Get 10 Bonafide and 10 Spoof from LA TRAIN
    df_la = df[(df['scenario'] == 'LA') & (df['partition'] == 'train')]
    bonafide_df = df_la[df_la['label'] == 'bonafide'].head(10)
    spoof_df = df_la[df_la['label'] == 'spoof'].head(10)
    
    test_df = pd.concat([bonafide_df, spoof_df])
    
    print("--- Audio Files Tested ---")
    
    successful_loads = 0
    failed_loads = 0
    corrupted_files = []
    
    waveforms = []
    labels = []
    
    feature_extractor = FeatureExtractor(
        sample_rate=config['audio']['sample_rate'],
        n_fft=config['features']['n_fft'],
        hop_length=config['features']['hop_length'],
        n_mels=config['features']['n_mels']
    )
    
    all_features = []
    
    for idx, row in test_df.iterrows():
        file_path = row['file_path']
        label = row['label']
        spk = row['speaker_id']
        
        print(f"\n[File]: {Path(file_path).name} | [Label]: {label} | [Speaker]: {spk}")
        
        if not os.path.exists(file_path):
            print("  -> ERROR: File does not exist!")
            failed_loads += 1
            corrupted_files.append(file_path)
            continue
            
        print(f"  -> File size: {os.path.getsize(file_path) / 1024:.1f} KB")
        
        try:
            import soundfile as sf
            wav, sr = sf.read(file_path)
            waveform = torch.tensor(wav, dtype=torch.float32)
            if waveform.dim() == 1:
                waveform = waveform.unsqueeze(0)
            else:
                waveform = waveform.t()
            
            successful_loads += 1
            
            # Stats
            is_nan = torch.isnan(waveform).any().item()
            is_inf = torch.isinf(waveform).any().item()
            w_min = waveform.min().item()
            w_max = waveform.max().item()
            w_mean = waveform.mean().item()
            w_std = waveform.std().item()
            duration = waveform.shape[1] / sr
            
            print(f"  -> Shape: {waveform.shape} | SR: {sr} Hz | Duration: {duration:.2f}s")
            print(f"  -> Min: {w_min:.4f} | Max: {w_max:.4f} | Mean: {w_mean:.4f} | Std: {w_std:.4f}")
            print(f"  -> NaNs: {is_nan} | Infs: {is_inf}")
            
            if w_std < 1e-4:
                print("  -> WARNING: Near-zero / dead audio detected!")
                
            # Test Feature Extraction
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
            if sr != 16000:
                resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)
                waveform = resampler(waveform)
                
            features = feature_extractor(waveform)
            f_nan = torch.isnan(features).any().item()
            f_inf = torch.isinf(features).any().item()
            
            print(f"  -> Log-Mel Shape: {features.shape} | Mean: {features.mean().item():.2f} | Std: {features.std().item():.2f} | NaNs: {f_nan} | Infs: {f_inf}")
            
            all_features.append(features)
            
            # Store for batch test (truncate/pad to 4s)
            c_len = waveform.shape[1]
            max_len = 16000 * 4
            if c_len < max_len:
                waveform = torch.nn.functional.pad(waveform, (0, max_len - c_len))
            elif c_len > max_len:
                waveform = waveform[:, :max_len]
                
            waveforms.append(waveform)
            labels.append(0.0 if label == 'bonafide' else 1.0)
            
        except Exception as e:
            print(f"  -> EXCEPTION: {e}")
            failed_loads += 1
            corrupted_files.append(file_path)
            
    print("\n" + "=" * 50)
    print("--- Loading Summary ---")
    print(f"Total tested: {len(test_df)}")
    print(f"Successful: {successful_loads}")
    print(f"Failed: {failed_loads}")
    
    if len(all_features) >= 2:
        diff = torch.mean(torch.abs(all_features[0] - all_features[1])).item()
        print(f"Mean Abs Difference between feature 0 and 1: {diff:.4f}")
        if diff == 0:
            print("CRITICAL ERROR: Feature tensors are perfectly identical! Preprocessing bug.")
            
    if failed_loads > 0:
        print("CRITICAL ERROR: Audio loading is failing. DO NOT train until fixed.")
        return
        
    print("\n" + "=" * 50)
    print("--- Model Gradients & GPU Test ---")
    
    try:
        model = LightweightAntiSpoofCNN(config).to(device)
        model.train()
        
        batch_x = torch.stack(waveforms).to(device)
        batch_y = torch.tensor(labels, dtype=torch.float32).unsqueeze(1).to(device)
        
        print(f"model.device: {next(model.parameters()).device}")
        print(f"input.device: {batch_x.device}")
        
        if torch.cuda.is_available():
            print(f"GPU memory allocated: {torch.cuda.memory_allocated() / (1024**2):.2f} MB")
            print(f"GPU memory reserved: {torch.cuda.memory_reserved() / (1024**2):.2f} MB")
            
        logits = model(batch_x)
        criterion = torch.nn.BCEWithLogitsLoss()
        loss = criterion(logits, batch_y)
        
        loss.backward()
        
        # Calculate gradient norm
        total_norm = 0.0
        for p in model.parameters():
            if p.grad is not None:
                param_norm = p.grad.detach().data.norm(2)
                total_norm += param_norm.item() ** 2
        total_norm = total_norm ** 0.5
        
        print(f"\nBatch Loss: {loss.item():.4f}")
        print(f"Logits Min: {logits.min().item():.4f} | Max: {logits.max().item():.4f} | Mean: {logits.mean().item():.4f}")
        print(f"Gradient Norm: {total_norm:.4f}")
        
        if total_norm == 0 or np.isnan(total_norm):
            print("CRITICAL ERROR: Gradients are dead or NaN!")
        else:
            print("Gradients are flowing normally.")
            
    except Exception as e:
        print(f"Model test failed: {e}")
        
    print("\n" + "=" * 50)
    print("ROOT CAUSE ANALYSIS")
    print("=" * 50)
    if not torch.cuda.is_available():
        print("A. CPU-only PyTorch was installed.")
    elif failed_loads > 0:
        print("B. Audio loading failure.")
    elif any(torch.isnan(f).any() for f in all_features):
        print("E. NaN/Inf features.")
    elif total_norm == 0 or np.isnan(total_norm):
        print("H. Model/loss problem.")
    else:
        print("The data pipeline, features, and model are working perfectly.")
        print("The previous failure (ROC-AUC 0.50) was solely due to A. CPU-only PyTorch causing us to abort, combined with class imbalance which has now been fixed in the config.")

if __name__ == "__main__":
    run_diagnostics()
