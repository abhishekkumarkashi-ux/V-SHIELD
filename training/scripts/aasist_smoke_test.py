import os
import sys
import time
import torch
import torch.nn as nn
import pandas as pd
import numpy as np
import soundfile as sf
import copy

# Ensure V-SHIELD is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from ml.models.aasist.model import AASIST
from ml.pipeline.preprocessing import sanitize_and_prepare_audio

def print_header(title):
    print("\n" + "="*60)
    print(title)
    print("="*60)

def print_failure(stage, cause, file=__file__, line=0, fix="", validation=""):
    print("\n" + "="*60)
    print("SMOKE TEST FAILED")
    print("="*60)
    print(f"FAILURE: {stage}")
    print(f"ROOT CAUSE: {cause}")
    print(f"FILE: {file}")
    print(f"LINE: {line}")
    print(f"FIX: {fix}")
    print(f"VALIDATION: {validation}")
    sys.exit(1)

def get_vram_info():
    if torch.cuda.is_available():
        alloc = torch.cuda.memory_allocated() / 1e9
        res = torch.cuda.memory_reserved() / 1e9
        peak = torch.cuda.max_memory_allocated() / 1e9
        return alloc, res, peak
    return 0, 0, 0

def run_smoke_test():
    # Kaggle paths from prompt
    manifest_path = "/kaggle/working/vshield_manifests/asvspoof2019_la_train.csv"
    checkpoint_path = "/kaggle/working/vshield_aasist_smoke_test.pt"
    batch_size = 2
    
    reports = {
        "CUDA": "FAIL",
        "Audio loading": "FAIL",
        "Preprocessing": "FAIL",
        "Forward pass": "FAIL",
        "Loss": "FAIL",
        "Backward": "FAIL",
        "Gradients": "FAIL",
        "Optimizer update": "FAIL",
        "AMP": "NOT IMPLEMENTED",
        "Checkpoint save": "FAIL",
        "Checkpoint reload": "FAIL",
        "Second forward": "FAIL",
    }
    
    print_header("STEP 1 — AUDIT EXISTING AASIST IMPLEMENTATION")
    print("AASIST model implementation: ml/models/aasist/model.py")
    print("Audio loading / Preprocessing: ml/pipeline/preprocessing.py")
    print("Expected sample rate: 16000")
    print("Expected waveform length: 64000 (4.0s)")
    print("Feature representation: Raw waveform -> SincConv")
    print("Output shape: (batch, 2) and (batch, 160)")
    print("Number of classes/logits: 2 (Bonafide=0, Spoof=1)")
    print("Loss function: nn.CrossEntropyLoss")
    print("Expected tensor dtype: torch.float32")
    
    # Initialize Model
    aasist_config = {
        "architecture": "AASIST",
        "filter_length": 128,
        "nb_samp": 64000,
        "first_conv": 128,
        "filts": [70, [1, 32], [32, 32], [32, 64], [64, 64]],
        "gat_dims": [64, 32],
        "pool_ratios": [0.5, 0.7, 0.5, 0.5],
        "temperatures": [2.0, 2.0, 100.0, 100.0]
    }
    model = AASIST(aasist_config)
    
    print_header("STEP 2 — VERIFY REAL AUDIO LOADING")
    try:
        if not os.path.exists(manifest_path):
            print_failure("Manifest missing", f"Could not find {manifest_path}", line=87, fix="Verify Kaggle paths")
            
        df = pd.read_csv(manifest_path)
        batch_df = df.head(batch_size)
        
        waveforms = []
        targets = []
        for _, row in batch_df.iterrows():
            audio_path = row['audio_path']
            label = row['label'] # 0 or 1
            
            if not os.path.exists(audio_path):
                print_failure("Audio missing", f"Could not find {audio_path}", line=97, fix="Check dataset extraction")
                
            wav, sr = sf.read(audio_path)
            if sr != 16000:
                print_failure("Sample rate", f"Expected 16000, got {sr}")
                
            tensor = sanitize_and_prepare_audio(wav, max_length=64000)
            waveforms.append(tensor)
            targets.append(label)
            
        batch_tensor = torch.cat(waveforms, dim=0) # (batch, 1, 64000)
        target_tensor = torch.tensor(targets, dtype=torch.long)
        
        print(f"Batch size: {batch_size}")
        print(f"Waveform shape: {batch_tensor.shape}")
        print(f"dtype: {batch_tensor.dtype}")
        print(f"Sample rate: 16000")
        print(f"Minimum: {batch_tensor.min().item():.4f}")
        print(f"Maximum: {batch_tensor.max().item():.4f}")
        print(f"Mean: {batch_tensor.mean().item():.4f}")
        print(f"Standard deviation: {batch_tensor.std().item():.4f}")
        print(f"Target tensor shape: {target_tensor.shape}")
        print(f"Target values: {target_tensor.tolist()}")
        
        assert not torch.isnan(batch_tensor).any(), "NaN found in audio"
        assert not torch.isinf(batch_tensor).any(), "Inf found in audio"
        
        reports["Audio loading"] = "PASS"
        reports["Preprocessing"] = "PASS"
    except Exception as e:
        print_failure("Audio loading", str(e))
        
    print_header("STEP 3 — GPU VERIFICATION")
    try:
        is_cuda = torch.cuda.is_available()
        print(f"CUDA available: {is_cuda}")
        if not is_cuda:
            print_failure("CUDA Check", "CUDA is not available on this machine")
            
        print(f"GPU count: {torch.cuda.device_count()}")
        print(f"GPU name: {torch.cuda.get_device_name(0)}")
        print(f"GPU memory (GB): {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f}")
        print(f"Current device: {torch.cuda.current_device()}")
        
        device = torch.device("cuda:0")
        model = model.to(device)
        batch_tensor = batch_tensor.to(device)
        target_tensor = target_tensor.to(device)
        
        assert next(model.parameters()).is_cuda, "Model not on CUDA"
        assert batch_tensor.is_cuda, "Batch not on CUDA"
        
        alloc, res, peak = get_vram_info()
        print(f"Allocated VRAM: {alloc:.3f} GB, Reserved: {res:.3f} GB")
        
        reports["CUDA"] = "PASS"
    except Exception as e:
        print_failure("CUDA placement", str(e))
        
    print_header("STEP 4 — REAL FORWARD PASS")
    try:
        model.eval()
        with torch.no_grad():
            logits, embs = model(batch_tensor)
            
        print(f"Input shape: {batch_tensor.shape}")
        print(f"Logits shape: {logits.shape}")
        print(f"Logits dtype: {logits.dtype}")
        print(f"Logits min: {logits.min().item():.4f}")
        print(f"Logits max: {logits.max().item():.4f}")
        print(f"Logits mean: {logits.mean().item():.4f}")
        print(f"Logits std: {logits.std().item():.4f}")
        
        assert not torch.isnan(logits).any(), "NaN in logits"
        assert not torch.isinf(logits).any(), "Inf in logits"
        
        reports["Forward pass"] = "PASS"
    except Exception as e:
        print_failure("Forward pass", str(e))
        
    print_header("STEP 5 — REAL LOSS")
    try:
        model.train()
        
        # Binary classification via 2-class CrossEntropyLoss
        # Since dataset is 90% spoof, we could use class weights.
        # For the smoke test, we verify the loss setup.
        # Class 0: Bonafide (2580), Class 1: Spoof (22800) -> Weights approx 8.84 and 1.0
        weight = torch.tensor([8.84, 1.0], device=device, dtype=torch.float32)
        criterion = nn.CrossEntropyLoss(weight=weight)
        
        logits, embs = model(batch_tensor)
        loss = criterion(logits, target_tensor)
        
        print(f"Loss function: CrossEntropyLoss with weights {weight.tolist()}")
        print(f"Loss: {loss.item():.4f}")
        print(f"Loss dtype: {loss.dtype}")
        print(f"Loss is finite: {torch.isfinite(loss).item()}")
        
        assert torch.isfinite(loss), "Loss is not finite"
        
        reports["Loss"] = "PASS"
    except Exception as e:
        print_failure("Loss", str(e))
        
    print_header("STEP 6 — BACKWARD PASS")
    try:
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
        optimizer.zero_grad()
        loss.backward()
        
        total_params = sum(1 for _ in model.parameters())
        grad_params = sum(1 for p in model.parameters() if p.grad is not None)
        nan_grads = sum(1 for p in model.parameters() if p.grad is not None and torch.isnan(p.grad).any())
        inf_grads = sum(1 for p in model.parameters() if p.grad is not None and torch.isinf(p.grad).any())
        
        max_grad = 0.0
        for p in model.parameters():
            if p.grad is not None:
                max_grad = max(max_grad, p.grad.abs().max().item())
                
        print(f"Number of trainable parameters: {total_params}")
        print(f"Number of parameters with gradients: {grad_params}")
        print(f"Number of parameters with NaN gradients: {nan_grads}")
        print(f"Number of parameters with Inf gradients: {inf_grads}")
        print(f"Maximum absolute gradient: {max_grad:.6f}")
        
        assert nan_grads == 0, "NaN gradients detected"
        assert inf_grads == 0, "Inf gradients detected"
        
        reports["Backward"] = "PASS"
        reports["Gradients"] = "PASS"
    except Exception as e:
        print_failure("Backward pass", str(e))
        
    print_header("STEP 7 — ONE REAL OPTIMIZER UPDATE")
    try:
        # Snapshot
        param_snapshot = {name: p.clone().detach() for name, p in model.named_parameters()}
        
        optimizer.step()
        
        changed = False
        for name, p in model.named_parameters():
            if not torch.equal(p, param_snapshot[name]):
                changed = True
                break
                
        print(f"Parameters changed = {changed}")
        assert changed, "Parameters did not change after optimizer step"
        
        reports["Optimizer update"] = "PASS"
    except Exception as e:
        print_failure("Optimizer update", str(e))
        
    print_header("STEP 8 — AMP / MIXED PRECISION TEST")
    try:
        optimizer.zero_grad()
        scaler = torch.amp.GradScaler('cuda')
        
        with torch.amp.autocast('cuda'):
            logits, embs = model(batch_tensor)
            loss_amp = criterion(logits, target_tensor)
            
        scaler.scale(loss_amp).backward()
        scaler.step(optimizer)
        scaler.update()
        
        assert torch.isfinite(loss_amp), "AMP loss is not finite"
        reports["AMP"] = "PASS"
    except Exception as e:
        print_failure("AMP", str(e))
        
    print_header("STEP 9 — CHECKPOINT TEST")
    try:
        checkpoint = {
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "epoch": 1,
            "config": aasist_config,
            "model_identifier": "AASIST",
            "dataset_identifier": "ASVspoof2019_LA",
            "timestamp": time.time()
        }
        torch.save(checkpoint, checkpoint_path)
        print(f"Saved checkpoint to {checkpoint_path}")
        reports["Checkpoint save"] = "PASS"
        
        # Fresh model
        fresh_model = AASIST(aasist_config).to(device)
        loaded = torch.load(checkpoint_path, map_location=device, weights_only=False)
        fresh_model.load_state_dict(loaded["model_state_dict"])
        reports["Checkpoint reload"] = "PASS"
        
        fresh_model.eval()
        with torch.no_grad():
            logits2, embs2 = fresh_model(batch_tensor)
            assert torch.isfinite(logits2).all(), "Loaded model logits are not finite"
        reports["Second forward"] = "PASS"
    except Exception as e:
        print_failure("Checkpoint test", str(e))
        
    print_header("STEP 10 — DATA LOADER REPEATABILITY")
    try:
        # Same logic
        wav2, _ = sf.read(batch_df.iloc[0]['audio_path'])
        tensor2 = sanitize_and_prepare_audio(wav2, max_length=64000)
        assert tensor2.shape == (1, 1, 64000)
        print("Data loader repeated successfully")
    except Exception as e:
        print_failure("DataLoader repeatability", str(e))
        
    print_header("STEP 11 — GPU MEMORY CHECK")
    alloc, res, peak = get_vram_info()
    print(f"Allocated VRAM: {alloc:.3f} GB")
    print(f"Reserved VRAM: {res:.3f} GB")
    print(f"Peak Allocated VRAM: {peak:.3f} GB")
    
    print_header("FINAL REPORT")
    all_pass = all(v in ["PASS", "NOT IMPLEMENTED"] for v in reports.values())
    
    print("="*60)
    print("V-SHIELD — AASIST GPU SMOKE TEST")
    print("="*60)
    print("Dataset:\nASVspoof 2019 LA\n")
    print("Real audio:\nYES\n")
    print("Model:\nml.models.aasist.model.AASIST\n")
    print(f"Device:\n{torch.cuda.get_device_name(0)}\n")
    
    for k, v in reports.items():
        print(f"{k}:\n{v}\n")
        
    print(f"GPU memory:\n{peak:.3f} GB\n")
    print("="*60)
    
    if all_pass:
        print("STATUS:\nREADY FOR FULL AASIST TRAINING")
    else:
        print("STATUS:\nNOT READY FOR FULL TRAINING")

if __name__ == "__main__":
    run_smoke_test()
