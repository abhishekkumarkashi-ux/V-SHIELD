import numpy as np
import scipy.signal

def simulate_mu_law_compression(audio_np):
    """
    Simulates G.711 mu-law compression commonly used in telephony.
    Non-linear quantization degradation.
    """
    if len(audio_np) == 0:
        return audio_np
        
    mu = 255.0
    
    # Compress
    compressed = np.sign(audio_np) * (np.log(1 + mu * np.abs(audio_np)) / np.log(1 + mu))
    
    # Quantize to 8-bit (256 levels)
    quantized = np.round(compressed * 127) / 127.0
    
    # Expand (Inverse mu-law)
    expanded = np.sign(quantized) * (1 / mu) * ((1 + mu) ** np.abs(quantized) - 1)
    
    return expanded

def apply_bandpass_filter(audio_np, sr, lowcut=300, highcut=3400):
    """
    Applies a bandpass filter to simulate telephone bandwidth (300Hz - 3400Hz).
    """
    nyq = 0.5 * sr
    low = lowcut / nyq
    high = highcut / nyq
    
    # Avoid errors if nyquist is violated
    if high >= 1.0:
        high = 0.99
        
    b, a = scipy.signal.butter(4, [low, high], btype='band')
    y = scipy.signal.lfilter(b, a, audio_np)
    return y
