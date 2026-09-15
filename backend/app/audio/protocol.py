"""
Audio streaming protocol definitions for V-SHIELD.
Defines the single source of truth for audio formats, windowing, and limits
shared between frontend and backend.
"""

AUDIO_PROTOCOL = {
    "SAMPLE_RATE": 16000,            # 16 kHz acoustic sampling
    "CHANNELS": 1,                   # Mono
    "DTYPE": "float32",              # 32-bit floating point PCM (-1.0 to 1.0)
    "BYTES_PER_SAMPLE": 4,           # 4 bytes per Float32
    "FRAME_CHUNK_SAMPLES": 16000,    # 1.0 second per client transmission
    "FRAME_CHUNK_BYTES": 64000,      # 16000 * 4 bytes = 64 KB
    "WINDOW_SIZE_SAMPLES": 64000,    # 4.0 seconds sliding analysis window
    "WINDOW_SIZE_SECONDS": 4.0,
    "HOP_SIZE_SAMPLES": 16000,       # 1.0 second evaluation hop
    "HOP_SIZE_SECONDS": 1.0,
    "OVERLAP_SAMPLES": 48000,        # 3.0 seconds retained buffer
    "OVERLAP_SECONDS": 3.0,
    "MAX_CHUNK_BYTES": 512 * 1024,   # 512 KB per frame ceiling (security guard)
    "MAX_BUFFER_SAMPLES": 160000,    # 10.0 seconds maximum buffer ceiling
    "MAX_SESSION_SECONDS": 3600,     # 1 hour maximum session duration
}
