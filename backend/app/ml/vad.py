import numpy as np

class EnergyVAD:
    def __init__(self, energy_threshold=0.01):
        """
        Initializes an Energy-based Voice Activity Detector.
        Args:
            energy_threshold (float): The RMS energy threshold. 
                                      0.01 is a typical value for normalized float32 audio.
        """
        self.energy_threshold = energy_threshold

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """
        Determines if an audio chunk contains speech based on RMS energy.
        Args:
            audio_chunk (np.ndarray): 1D float32 array of audio samples (-1.0 to 1.0).
        Returns:
            bool: True if speech is detected, False otherwise.
        """
        if len(audio_chunk) == 0:
            return False
            
        # Remove DC offset
        chunk_centered = audio_chunk - np.mean(audio_chunk)
        
        # Calculate Root Mean Square energy
        rms = np.sqrt(np.mean(np.square(chunk_centered)))
        
        return bool(rms > self.energy_threshold), float(rms)
