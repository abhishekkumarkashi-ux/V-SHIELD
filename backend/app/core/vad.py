"""
Margin-Preserving Voice Activity Detection (VAD) Guard (SIH 2026).
Mitigates ASVspoof 2021 Silence Shortcut Degradation:
Preserves 250ms - 300ms ambient silence margins around speech events.
Never hard-clips to phoneme/word boundaries to preserve AASIST spectro-temporal graph dynamics.
"""

from typing import Tuple, Union

import numpy as np
import torch


class MarginPreservingVAD:
    """
    VAD Segmenter designed specifically to safeguard AASIST against silence shortcut failure.
    Retains minimum 300ms (4800 samples @ 16kHz) leading and trailing ambient margins.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 25,
        energy_threshold: float = 0.005,
        min_silence_padding_sec: float = 0.30,
        min_speech_duration_ms: int = 50,
    ) -> None:
        self.sample_rate: int = sample_rate
        self.frame_len: int = int(sample_rate * (frame_duration_ms / 1000.0))  # 400 samples @ 16kHz
        self.energy_threshold: float = energy_threshold
        self.margin_samples: int = int(
            sample_rate * min_silence_padding_sec
        )  # 4,800 samples @ 16kHz
        self.min_speech_duration_ms: int = min_speech_duration_ms
        self.min_speech_frames: int = max(
            1, int(round((min_speech_duration_ms / 1000.0) / (frame_duration_ms / 1000.0)))
        )

    def compute_frame_energies(self, audio: np.ndarray) -> np.ndarray:
        """Computes frame-level RMS energy."""
        n_frames = len(audio) // self.frame_len
        if n_frames == 0:
            return np.array([float(np.sqrt(np.mean(audio**2)))])

        frames = audio[: n_frames * self.frame_len].reshape(n_frames, self.frame_len)
        rms_energies = np.sqrt(np.mean(frames**2, axis=1))
        return rms_energies

    def detect_speech_mask(self, audio: np.ndarray) -> np.ndarray:
        """
        Creates a boolean sample-level mask indicating speech regions,
        filtered for minimum speech duration and EXPANDED with leading and trailing silence margins.
        """
        if len(audio) == 0:
            return np.array([], dtype=bool)

        energies = self.compute_frame_energies(audio)
        raw_speech_frames = energies > self.energy_threshold

        # Filter out isolated transient clicks shorter than min_speech_frames
        filtered_frames = np.copy(raw_speech_frames)
        if self.min_speech_frames > 1:
            run_length = 0
            for i, is_speech in enumerate(raw_speech_frames):
                if is_speech:
                    run_length += 1
                else:
                    if 0 < run_length < self.min_speech_frames:
                        filtered_frames[i - run_length : i] = False
                    run_length = 0
            if 0 < run_length < self.min_speech_frames:
                filtered_frames[len(raw_speech_frames) - run_length :] = False

        # Map back to sample-level mask
        sample_mask = np.zeros(len(audio), dtype=bool)

        for i, is_speech in enumerate(filtered_frames):
            if is_speech:
                start_sample = i * self.frame_len
                end_sample = min((i + 1) * self.frame_len, len(audio))
                sample_mask[start_sample:end_sample] = True

        if not np.any(sample_mask):
            return sample_mask

        # Dilate the speech mask with min_silence_padding (250-300ms) on each side
        expanded_mask = np.copy(sample_mask)
        speech_indices = np.where(sample_mask)[0]

        if len(speech_indices) > 0:
            first_speech = max(0, speech_indices[0] - self.margin_samples)
            last_speech = min(len(audio), speech_indices[-1] + self.margin_samples)
            expanded_mask[first_speech:last_speech] = True

        return expanded_mask

    def analyze_speech(self, audio: Union[np.ndarray, torch.Tensor]) -> dict:
        """
        Computes detailed acoustic and VAD metrics for diagnostics, logs, and telemetry.
        Distinguishes SPEECH from SILENCE with frame-level resolution.
        """
        if isinstance(audio, torch.Tensor):
            audio_np = audio.detach().cpu().squeeze().numpy()
        else:
            audio_np = np.asarray(audio, dtype=np.float32).flatten()

        energies = self.compute_frame_energies(audio_np)
        active_raw = energies > self.energy_threshold
        active_frames = int(np.sum(active_raw))
        total_frames = len(energies)

        mask = self.detect_speech_mask(audio_np)
        speech_ratio = float(np.mean(mask)) if len(mask) > 0 else 0.0
        is_speech_active = speech_ratio > 0.05

        return {
            "state": "SPEECH" if is_speech_active else "SILENCE",
            "is_speech_active": is_speech_active,
            "speech_ratio": round(speech_ratio, 4),
            "mean_frame_rms": round(float(np.mean(energies)), 6) if len(energies) > 0 else 0.0,
            "peak_frame_rms": round(float(np.max(energies)), 6) if len(energies) > 0 else 0.0,
            "active_frames_count": active_frames,
            "total_frames_count": total_frames,
            "speech_duration_ms": round(
                (active_frames * self.frame_len / self.sample_rate) * 1000.0, 2
            ),
            "energy_threshold": self.energy_threshold,
            "sample_rate": self.sample_rate,
            "frame_len": self.frame_len,
            "margin_samples": self.margin_samples,
        }

    def process_window(
        self, audio: Union[np.ndarray, torch.Tensor]
    ) -> Tuple[bool, float, torch.Tensor]:
        """
        Analyzes the 64,600 sample window.
        Returns:
            - is_speech_active (bool): Whether speech is present in window.
            - speech_ratio (float): Ratio of active speech (inclusive of preserved margins).
            - safe_audio (torch.Tensor): Window with preserved margins, ready for AASIST.
        """
        if isinstance(audio, torch.Tensor):
            audio_np = audio.detach().cpu().squeeze().numpy()
        else:
            audio_np = np.asarray(audio, dtype=np.float32).flatten()

        mask = self.detect_speech_mask(audio_np)
        speech_ratio = float(np.mean(mask)) if len(mask) > 0 else 0.0
        is_speech_active = speech_ratio > 0.05

        # Crucial: AASIST requires full continuous 64,600 tensor.
        # We do NOT hard-trim or chop the audio tensor; we pass the complete
        # context preserved tensor with zero-clipping of silence transitions.
        if isinstance(audio, torch.Tensor):
            safe_tensor = audio
        else:
            safe_tensor = torch.from_numpy(audio_np).unsqueeze(0).to(torch.float32)

        return is_speech_active, speech_ratio, safe_tensor
