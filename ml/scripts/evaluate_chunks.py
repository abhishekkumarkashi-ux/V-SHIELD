import os
import sys
import torch
import yaml
import numpy as np
from tqdm import tqdm
from sklearn.metrics import accuracy_score

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dataset import ASVSpoofDataset
from model import LightweightAntiSpoofCNN
from robustness.chunk_tests import generate_chunks

def main():
    # We append backend path to use RiskEngine for testing EMA
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend')))
    from app.risk.risk_engine import RiskEngine
    
    with open("ml/config.yaml", "r") as f:
        config = yaml.safe_load(f)
        
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Running chunk evaluation on {device}")
    
    model = LightweightAntiSpoofCNN(config).to(device)
    model.load_state_dict(torch.load("models/vshield_antispoof_v1/model.pt", map_location=device, weights_only=True))
    model.eval()
    
    metadata_path = os.path.join(config['dataset']['metadata_dir'], "asvspoof_metadata.csv")
    dataset = ASVSpoofDataset(metadata_path, partition="dev", config=config)
    
    # Evaluate a few samples
    num_samples_to_test = 50
    total_chunks = 0
    correct_chunks = 0
    
    print("\n--- Evaluating Real-Time Chunks (3.0s window, 1.5s step) ---")
    
    with torch.no_grad():
        for i in range(min(num_samples_to_test, len(dataset))):
            waveform, label = dataset[i]
            label = label.item()
            np_audio = waveform.squeeze().numpy()
            
            risk_engine = RiskEngine(alpha=0.3)
            
            chunks = list(generate_chunks(np_audio, sr=16000, window_sec=3.0, step_sec=1.5))
            
            for start, end, chunk_data in chunks:
                if len(chunk_data) < 16000 * 0.1: # Skip very small chunks
                    continue
                    
                # Pad to 4 seconds for model input if necessary
                target_len = int(config['audio']['duration_sec'] * 16000)
                if len(chunk_data) < target_len:
                    chunk_data = np.pad(chunk_data, (0, target_len - len(chunk_data)), "constant")
                else:
                    chunk_data = chunk_data[:target_len]
                
                chunk_tensor = torch.tensor(chunk_data, dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(device)
                logits = model(chunk_tensor)
                score = torch.sigmoid(logits).item()
                
                risk_payload = risk_engine.calculate_risk_score(score)
                pred = 1 if risk_payload['risk_score'] >= 0.5 else 0
                
                if pred == label:
                    correct_chunks += 1
                total_chunks += 1
                
    print(f"\nTested {total_chunks} chunks over {min(num_samples_to_test, len(dataset))} audio files.")
    if total_chunks > 0:
        print(f"Chunk-level accuracy with EMA Risk Engine: {correct_chunks / total_chunks:.4f}")
    
    with open("ml/reports/robustness/chunk_metrics.yaml", "w") as f:
        yaml.dump({
            "chunk_accuracy": correct_chunks / total_chunks if total_chunks > 0 else 0,
            "total_chunks_tested": total_chunks
        }, f)

if __name__ == "__main__":
    main()
