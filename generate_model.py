import os
import sys
import torch

# Add V-SHIELD/ml to path
base_dir = os.path.dirname(os.path.abspath(__file__))
ml_src_dir = os.path.join(base_dir, 'ml', 'src')
sys.path.append(ml_src_dir)

from model import LightweightAntiSpoofCNN

def generate_dummy_model():
    print("Initializing LightweightAntiSpoofCNN...")
    model = LightweightAntiSpoofCNN()
    
    # Save the state_dict
    output_dir = os.path.join(base_dir, 'models', 'vshield_antispoof_v1')
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, 'best_model.pt')
    torch.save(model.state_dict(), output_path)
    print(f"Dummy model saved successfully to: {output_path}")

if __name__ == "__main__":
    generate_dummy_model()
