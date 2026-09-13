import torch
import torch.nn as nn
from features import FeatureExtractor

class LightweightAntiSpoofCNN(nn.Module):
    def __init__(self, config=None):
        super().__init__()
        
        # Load feature config
        sr = config['audio']['sample_rate'] if config else 16000
        n_fft = config['features']['n_fft'] if config else 512
        hop_length = config['features']['hop_length'] if config else 160
        n_mels = config['features']['n_mels'] if config else 80
        
        # 1. Feature Extractor as part of the model graph
        self.feature_extractor = FeatureExtractor(
            sample_rate=sr, n_fft=n_fft, hop_length=hop_length, n_mels=n_mels
        )
        
        # 2. CNN Backbone (Lightweight)
        self.conv_blocks = nn.Sequential(
            # Block 1
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            
            # Block 2
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            
            # Block 3
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )
        
        # 3. Global Average Pooling (handles variable time lengths safely)
        self.global_pool = nn.AdaptiveAvgPool2d((1, 1))
        
        # 4. Classifier Head
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(32, 1) # Single output for BCEWithLogitsLoss
        )

    def forward(self, waveform):
        # Force feature extraction in FP32 to prevent STFT FP16 NaN overflow
        with torch.amp.autocast('cuda', enabled=False):
            features = self.feature_extractor(waveform)

        
        # Features output: (batch, 1, n_mels, frames)
        x = self.conv_blocks(features)
        
        # GAP output: (batch, 64, 1, 1)
        x = self.global_pool(x)
        
        # Classifier output: (batch, 1)
        logits = self.classifier(x)
        return logits
