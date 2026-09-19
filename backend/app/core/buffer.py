"""
Circular Sliding Ring Buffer for Real-Time Audio Streaming (SIH 2026).
Maintains 64,600 samples (~4.0375s @ 16 kHz) and yields (1, 64600) PyTorch tensors
every 8,000 samples (~0.5s hop).
"""

import threading
from typing import Generator, Optional

import numpy as np
import torch
from scipy import signal


class AudioCircularBuffer:
    """
    Thread-safe circular ring buffer designed for streaming inference with AASIST.
    Buffer capacity: 64,600 samples (at 16 kHz mono).
    Hop size: 8,000 samples (0.5 seconds).
    """

    def __init__(
        self,
        capacity: int = 64600,
        hop_size: int = 8000,
        target_sample_rate: int = 16000,
    ) -> None:
        self.capacity: int = capacity
        self.hop_size: int = hop_size
        self.target_sample_rate: int = target_sample_rate

        self._lock = threading.Lock()
        self._buffer: np.ndarray = np.zeros(self.capacity, dtype=np.float32)
        self._samples_accumulated_since_hop: int = 0
        self._total_samples_written: int = 0
        self._is_primed: bool = False

    def reset(self) -> None:
        """Resets buffer state and zero-fills memory."""
        with self._lock:
            self._buffer.fill(0.0)
            self._samples_accumulated_since_hop = 0
            self._total_samples_written = 0
            self._is_primed = False

    def append_pcm16_bytes(self, pcm_bytes: bytes, input_sample_rate: Optional[int] = None) -> None:
        """
        Ingests raw little-endian PCM16 bytes, normalizes to [-1.0, 1.0] float32,
        upsamples from 8 kHz narrowband if necessary, and writes to buffer.
        """
        if not pcm_bytes:
            return

        # Ensure complete 16-bit 2-byte frames
        valid_len = (len(pcm_bytes) // 2) * 2
        if valid_len == 0:
            return

        int16_data = np.frombuffer(pcm_bytes[:valid_len], dtype=np.int16)
        float_data = int16_data.astype(np.float32) / 32768.0

        # Narrowband Telephony Handling: Upsample 8 kHz PSTN / Asterisk input to 16 kHz mono
        rate = input_sample_rate or self.target_sample_rate
        if rate == 8000:
            float_data = signal.resample_poly(float_data, up=2, down=1).astype(np.float32)
        elif rate != self.target_sample_rate:
            # General rational resampling
            from math import gcd

            common = gcd(rate, self.target_sample_rate)
            up = self.target_sample_rate // common
            down = rate // common
            float_data = signal.resample_poly(float_data, up=up, down=down).astype(np.float32)

        self.append_samples(float_data)

    def append_samples(self, samples: np.ndarray) -> None:
        """
        Appends float32 1D numpy array into the circular sliding ring buffer.
        """
        if len(samples) == 0:
            return

        with self._lock:
            n_samples = len(samples)
            if n_samples >= self.capacity:
                # If incoming chunk exceeds buffer, keep the most recent window
                self._buffer[:] = samples[-self.capacity :]
            else:
                # Shift left and append new samples to the right
                self._buffer[:-n_samples] = self._buffer[n_samples:]
                self._buffer[-n_samples:] = samples

            self._samples_accumulated_since_hop += n_samples
            self._total_samples_written += n_samples

            if self._total_samples_written >= self.capacity:
                self._is_primed = True

    def can_extract(self) -> bool:
        """
        Returns True if the buffer has filled at least one hop step.
        """
        with self._lock:
            return self._is_primed and (self._samples_accumulated_since_hop >= self.hop_size)

    def extract_window(self) -> Optional[torch.Tensor]:
        """
        If a hop step is ready, returns a (1, 64600) PyTorch tensor,
        advancing the internal hop counter. Returns None if not ready.
        """
        with self._lock:
            if not self._is_primed or self._samples_accumulated_since_hop < self.hop_size:
                return None

            self._samples_accumulated_since_hop -= self.hop_size
            window_copy = np.copy(self._buffer)

        # Reshape to (1, capacity) as required by AASIST
        tensor = torch.from_numpy(window_copy).unsqueeze(0).to(torch.float32)
        return tensor

    def extract_all_ready_windows(self) -> Generator[torch.Tensor, None, None]:
        """
        Yields (1, 64600) PyTorch tensors for each complete hop interval accumulated.
        """
        while self.can_extract():
            win = self.extract_window()
            if win is not None:
                yield win

    def get_current_rms(self) -> float:
        """
        Calculates Root-Mean-Square energy of the current buffer.
        """
        with self._lock:
            if self._total_samples_written == 0:
                return 0.0
            mean_sq = np.mean(self._buffer**2)
            return float(np.sqrt(mean_sq))

    @property
    def is_primed(self) -> bool:
        with self._lock:
            return self._is_primed

    @property
    def total_samples(self) -> int:
        with self._lock:
            return self._total_samples_written
