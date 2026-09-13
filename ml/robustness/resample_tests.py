import numpy as np
import scipy.signal

def simulate_resampling(audio_np, orig_sr, target_sr):
    """
    Simulates sending audio over a lower sample rate channel, 
    then resampling back up to the original sample rate.
    """
    if orig_sr == target_sr or len(audio_np) == 0:
        return audio_np
        
    # Number of samples after downsampling
    num_downsampled = int(len(audio_np) * float(target_sr) / orig_sr)
    
    # Downsample
    downsampled = scipy.signal.resample(audio_np, num_downsampled)
    
    # Upsample back to original
    reconstructed = scipy.signal.resample(downsampled, len(audio_np))
    
    return reconstructed
