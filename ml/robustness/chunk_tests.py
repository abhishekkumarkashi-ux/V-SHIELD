import numpy as np

def generate_chunks(audio_np, sr, window_sec, step_sec):
    """
    Splits a continuous audio array into overlapping chunks.
    Yields (start_idx, end_idx, chunk_data)
    """
    window_size = int(window_sec * sr)
    step_size = int(step_sec * sr)
    
    if len(audio_np) < window_size:
        yield 0, len(audio_np), audio_np
        return
        
    start = 0
    while start + window_size <= len(audio_np):
        end = start + window_size
        yield start, end, audio_np[start:end]
        start += step_size
        
    # Handle the final remainder
    if start < len(audio_np):
        yield start, len(audio_np), audio_np[start:]
