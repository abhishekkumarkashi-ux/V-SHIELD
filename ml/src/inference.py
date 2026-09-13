import os
import sys
import torch
import soundfile as sf

def main():
    if len(sys.argv) < 2:
        print("Usage: python inference.py <path_to_audio>")
        sys.exit(1)
        
    audio_path = sys.argv[1]
    
    # 1. Load config and set up path
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    model_path = os.path.join(base_dir, 'models', 'vshield_antispoof_v1', 'best_model.pt')
    
    # 2. Import model and risk score
    from model import LightweightAntiSpoofCNN
    from risk_score import calculate_risk_score
    
    # 3. Load model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading model on {device}...")
    model = LightweightAntiSpoofCNN()
    state_dict = torch.load(model_path, map_location=device, weights_only=True)
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    
    # 4. Load Audio
    print(f"Loading audio: {audio_path}")
    wav, sr = sf.read(audio_path)
    waveform = torch.tensor(wav, dtype=torch.float32)
    if waveform.dim() == 1:
        waveform = waveform.unsqueeze(0)
    else:
        waveform = waveform.t()
        
    if waveform.shape[0] > 1:
        waveform = torch.mean(waveform, dim=0, keepdim=True)
        
    max_length = 16000 * 4
    if waveform.shape[1] < max_length:
        padding = max_length - waveform.shape[1]
        waveform = torch.nn.functional.pad(waveform, (0, padding))
    else:
        waveform = waveform[:, :max_length]
        
    max_val = torch.max(torch.abs(waveform))
    if max_val > 0:
        waveform = waveform / max_val
        
    waveform = waveform.unsqueeze(0).to(device)
    
    # 5. Inference
    with torch.inference_mode():
        logits = model(waveform)
        prob = torch.sigmoid(logits).item()
        
    # 6. Risk Score
    result = calculate_risk_score(prob)
    print("\n--- INFERENCE RESULT ---")
    for k, v in result.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()
