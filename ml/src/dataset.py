import os
import torch
import torchaudio
import pandas as pd
from torch.utils.data import Dataset

class ASVSpoofDataset(Dataset):
    def __init__(self, metadata_path, partition="train", config=None):
        self.df = pd.read_csv(metadata_path)
        
        # Enforce Logical Access only
        scenario = config['training'].get('scenario', 'LA') if config else 'LA'
        self.df = self.df[self.df['scenario'] == scenario]
        
        # Filter by partition
        self.df = self.df[self.df['partition'] == partition]
        
        # Filter out missing files
        self.df = self.df[self.df['file_path'].notna() & (self.df['file_path'] != "")]
        
        # Only keep rows with labels
        self.df = self.df[self.df['label'].isin(['bonafide', 'spoof'])]
            
        if config and config['training'].get('balanced_subset', False):
            if partition == "train":
                req_bonafide = config['training']['train_bonafide']
                req_spoof = config['training']['train_spoof']
            else:
                req_bonafide = config['training']['val_bonafide']
                req_spoof = config['training']['val_spoof']
                
            df_bonafide = self.df[self.df['label'] == 'bonafide']
            df_spoof = self.df[self.df['label'] == 'spoof']
            
            # Use replace=True if we request more samples than exist in the set
            df_bonafide_sampled = df_bonafide.sample(req_bonafide, replace=(len(df_bonafide) < req_bonafide), random_state=42)
            df_spoof_sampled = df_spoof.sample(req_spoof, replace=(len(df_spoof) < req_spoof), random_state=42)
            
            self.df = pd.concat([df_bonafide_sampled, df_spoof_sampled])
            
        self.df = self.df.sample(frac=1, random_state=42).reset_index(drop=True) # Shuffle
        
        self.sample_rate = config['audio']['sample_rate'] if config else 16000
        self.max_duration = config['audio']['duration_sec'] if config else 4.0
        self.max_length = int(self.sample_rate * self.max_duration)
        
    def __len__(self):
        return len(self.df)
        
    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        file_path = row['file_path']
        
        # Explicit Mapping: 0 = bonafide, 1 = spoof
        label = 0.0 if row['label'] == 'bonafide' else 1.0
        
        try:
            import soundfile as sf
            wav, sr = sf.read(file_path)
            waveform = torch.tensor(wav, dtype=torch.float32)
            if waveform.dim() == 1:
                waveform = waveform.unsqueeze(0)
            else:
                waveform = waveform.t()
            
            # Convert to mono
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
                
            # Resample
            if sr != self.sample_rate:
                resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=self.sample_rate)
                waveform = resampler(waveform)
                
            # Normalize
            max_val = torch.max(torch.abs(waveform))
            if max_val > 0:
                waveform = waveform / max_val
                
            # Pad / Truncate
            c_len = waveform.shape[1]
            if c_len < self.max_length:
                waveform = torch.nn.functional.pad(waveform, (0, self.max_length - c_len))
            elif c_len > self.max_length:
                waveform = waveform[:, :self.max_length]
                
        except Exception as e:
            print(f"WARNING: Audio loading failed for {file_path}. Error: {e}. Skipping safely.")
            import random
            return self.__getitem__(random.randint(0, len(self.df) - 1))
            
        return waveform, torch.tensor([label], dtype=torch.float32)
