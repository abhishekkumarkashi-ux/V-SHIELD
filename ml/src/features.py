import torch
import torch.nn as nn
import torchaudio

class FeatureExtractor(nn.Module):
    def __init__(self, sample_rate=16000, n_fft=512, hop_length=160, n_mels=80):
        super().__init__()
        self.mel_spec = torchaudio.transforms.MelSpectrogram(
            sample_rate=sample_rate,
            n_fft=n_fft,
            hop_length=hop_length,
            n_mels=n_mels
        )
        self.amplitude_to_db = torchaudio.transforms.AmplitudeToDB()

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        """
        Extracts Log-Mel Spectrogram from audio waveform.
        Input: (batch, 1, time)
        Output: (batch, 1, n_mels, frames)
        """
        mel = self.mel_spec(waveform)
        log_mel = self.amplitude_to_db(mel)
        return log_mel
