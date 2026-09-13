import numpy as np

def add_white_noise(audio_np, snr_db):
    """
    Adds white Gaussian noise to audio at a specific Signal-to-Noise Ratio (SNR).
    """
    if len(audio_np) == 0:
        return audio_np
        
    # Calculate signal power
    signal_power = np.mean(audio_np ** 2)
    if signal_power == 0:
        return audio_np # Cannot add noise to pure silence based on SNR
        
    # Calculate noise power required for SNR
    # SNR = 10 * log10(signal_power / noise_power)
    # noise_power = signal_power / (10 ** (SNR / 10))
    noise_power = signal_power / (10 ** (snr_db / 10))
    
    # Generate noise
    noise = np.random.normal(0, np.sqrt(noise_power), len(audio_np))
    
    # Add noise to signal
    noisy_signal = audio_np + noise
    
    # Normalize to avoid clipping if necessary
    max_val = np.max(np.abs(noisy_signal))
    if max_val > 1.0:
        noisy_signal = noisy_signal / max_val
        
    return noisy_signal
