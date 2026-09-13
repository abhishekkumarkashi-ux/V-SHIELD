import numpy as np

def change_volume(audio_np, db_change):
    """
    Changes the volume of the audio by a specific dB value.
    db_change > 0 increases volume.
    db_change < 0 decreases volume.
    """
    if len(audio_np) == 0:
        return audio_np
        
    # Linear gain = 10 ^ (dB / 20)
    gain = 10 ** (db_change / 20.0)
    
    scaled_signal = audio_np * gain
    
    # Clip to [-1.0, 1.0] if exceeds boundaries
    scaled_signal = np.clip(scaled_signal, -1.0, 1.0)
    
    return scaled_signal
