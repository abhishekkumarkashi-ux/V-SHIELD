"""
Unit tests for AudioCircularBuffer (SIH 2026).
Verifies circular buffering, PCM16 conversion, hop triggers, and tensor shapes.
"""

import numpy as np

try:
    import pytest
except ImportError:
    pytest = None
import torch
from app.core.buffer import AudioCircularBuffer


def test_buffer_initialization():
    buf = AudioCircularBuffer(capacity=64600, hop_size=8000)
    assert not buf.is_primed
    assert not buf.can_extract()
    assert buf.total_samples == 0
    assert buf.extract_window() is None


def test_buffer_pcm16_ingestion():
    buf = AudioCircularBuffer(capacity=64600, hop_size=8000)

    # Generate 16,000 samples of 16-bit PCM (1 second of audio)
    raw_int16 = np.random.randint(-32768, 32767, size=16000, dtype=np.int16)
    pcm_bytes = raw_int16.tobytes()

    buf.append_pcm16_bytes(pcm_bytes)
    assert buf.total_samples == 16000
    assert not buf.is_primed  # Needs 64,600 to prime


def test_buffer_priming_and_hop_cadence():
    capacity = 64600
    hop = 8000
    buf = AudioCircularBuffer(capacity=capacity, hop_size=hop)

    # Ingest exactly capacity (64,600 samples)
    data = np.ones(capacity, dtype=np.float32) * 0.5
    buf.append_samples(data)

    assert buf.is_primed
    assert buf.can_extract()

    # Extract first window
    win = buf.extract_window()
    assert win is not None
    assert isinstance(win, torch.Tensor)
    assert win.shape == (1, capacity)
    assert torch.allclose(win, torch.tensor(0.5, dtype=torch.float32))

    # Next extraction should require accumulating another hop (8,000 samples)
    # Since 64,600 samples were written, accumulated samples is 64,600 - 8,000 = 56,600
    # Additional extraction possible until accumulated < hop
    extracted_count = 1
    while buf.can_extract():
        w = buf.extract_window()
        assert w is not None
        extracted_count += 1

    assert extracted_count == (capacity // hop)


def test_buffer_sliding_window_rollover():
    capacity = 1000
    hop = 200
    buf = AudioCircularBuffer(capacity=capacity, hop_size=hop)

    # Write initial 1000 zeros
    buf.append_samples(np.zeros(capacity, dtype=np.float32))
    assert buf.is_primed

    # Extract primed windows to reset hop counter
    while buf.can_extract():
        buf.extract_window()

    # Append 200 ones
    new_data = np.ones(hop, dtype=np.float32)
    buf.append_samples(new_data)
    assert buf.can_extract()

    win = buf.extract_window()
    assert win is not None
    arr = win.squeeze(0).numpy()
    # The first 800 should be 0.0, the last 200 should be 1.0
    assert np.all(arr[:800] == 0.0)
    assert np.all(arr[800:] == 1.0)


def test_narrowband_8khz_upsampling():
    buf = AudioCircularBuffer(capacity=64600, hop_size=8000, target_sample_rate=16000)

    # 4000 samples @ 8 kHz should become 8000 samples @ 16 kHz
    int16_8k = np.random.randint(-16000, 16000, size=4000, dtype=np.int16)
    buf.append_pcm16_bytes(int16_8k.tobytes(), input_sample_rate=8000)

    assert buf.total_samples == 8000
