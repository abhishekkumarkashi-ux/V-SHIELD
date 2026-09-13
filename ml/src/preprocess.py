import torch
import torchaudio

class AudioPreprocessor:
    def __init__(self, target_sample_rate=16000, max_duration_sec=4.0):
        self.target_sample_rate = target_sample_rate
        self.max_length = int(target_sample_rate * max_duration_sec)

    def process(self, waveform: torch.Tensor, sample_rate: int) -> torch.Tensor:
        """
        Preprocesses audio tensor to be mono, at target sample rate, 
        and fixed length (padded or truncated).
        """
        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
            
        # Resample if needed
        if sample_rate != self.target_sample_rate:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=self.target_sample_rate)
            waveform = resampler(waveform)
            
        # Normalize amplitude to [-1, 1]
        max_val = torch.max(torch.abs(waveform))
        if max_val > 0:
            waveform = waveform / max_val
            
        # Pad or truncate
        current_length = waveform.shape[1]
        if current_length < self.max_length:
            padding = self.max_length - current_length
            waveform = torch.nn.functional.pad(waveform, (0, padding))
        elif current_length > self.max_length:
            waveform = waveform[:, :self.max_length]
            
        return waveform
