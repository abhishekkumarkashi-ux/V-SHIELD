import { useState, useRef, useCallback } from 'react';
import { AudioCapture, AudioDebugInfo } from '../audio/AudioCapture';

interface UseAudioStreamerProps {
  onAudioChunk: (pcmChunk: ArrayBuffer) => void;
  targetSampleRate?: number;
}

export function useAudioStreamer({
  onAudioChunk,
  targetSampleRate = 16000,
}: UseAudioStreamerProps) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [rmsVolume, setRmsVolume] = useState(0);
  const [debugInfo, setDebugInfo] = useState<AudioDebugInfo | null>(null);

  const audioCaptureRef = useRef<AudioCapture | null>(null);
  const simulationIntervalRef = useRef<number | null>(null);

  const startStreaming = useCallback(async () => {
    try {
      if (audioCaptureRef.current) {
        audioCaptureRef.current.stop();
        audioCaptureRef.current = null;
      }

      const capture = new AudioCapture({
        targetSampleRate,
        chunkSamples: 2048,
        onAudioChunk: (pcmFloat32, debug) => {
          setDebugInfo(debug);
          onAudioChunk(pcmFloat32);
        },
        onVolumeChange: (vol) => {
          setRmsVolume(vol);
        },
      });

      const initialDebug = await capture.start();
      audioCaptureRef.current = capture;
      setDebugInfo(initialDebug);
      setIsStreaming(true);
      setIsMuted(false);
    } catch (err) {
      console.error('[AudioStreamer] Microphone capture initialization failed:', err);
      throw err;
    }
  }, [onAudioChunk, targetSampleRate]);

  const stopStreaming = useCallback(() => {
    if (simulationIntervalRef.current) {
      clearInterval(simulationIntervalRef.current);
      simulationIntervalRef.current = null;
    }

    if (audioCaptureRef.current) {
      audioCaptureRef.current.stop();
      audioCaptureRef.current = null;
    }

    setIsStreaming(false);
    setRmsVolume(0);
    setDebugInfo(null);
  }, []);

  const toggleMute = useCallback(() => {
    setIsMuted((prev) => !prev);
  }, []);

  // Simulation mode streaming raw Float32 PCM at 16 kHz
  const startSimulation = useCallback(
    (type: 'genuine' | 'clone' | 'unknown') => {
      stopStreaming();
      setIsStreaming(true);

      const chunkSize = 2048;
      let phase = 0;

      const simDebug: AudioDebugInfo = {
        inputSampleRate: targetSampleRate,
        targetSampleRate,
        channelCount: 1,
        chunkSamples: chunkSize,
        chunkDurationMs: Math.round((chunkSize / targetSampleRate) * 1000),
        rmsVolume: 0.25,
        isWorklet: false,
        microphoneStatus: 'IDLE',
        chunksSent: 0,
        bytesSent: 0,
      };
      setDebugInfo(simDebug);

      simulationIntervalRef.current = window.setInterval(() => {
        const buffer = new Float32Array(chunkSize);
        for (let i = 0; i < chunkSize; i++) {
          phase += 0.05;
          if (type === 'genuine') {
            // Harmonic human speech simulation
            buffer[i] =
              (Math.sin(phase) * 0.4 +
                Math.sin(phase * 2.2) * 0.2 +
                Math.sin(phase * 3.7) * 0.1) *
              (0.5 + 0.5 * Math.sin(phase * 0.05));
          } else if (type === 'clone') {
            // Synthetic robotic vocoder modulation
            buffer[i] =
              (Math.sin(phase * 1.5) * 0.35 +
                Math.sin(phase * 4.5) * 0.25 +
                (Math.random() - 0.5) * 0.15);
          } else {
            // Uncorrelated acoustic noise
            buffer[i] = (Math.random() - 0.5) * 0.3;
          }
        }

        setRmsVolume(0.25);
        // Transmit raw 16kHz Float32 PCM ArrayBuffer
        onAudioChunk(buffer.buffer);
      }, 128); // Every ~128ms
    },
    [onAudioChunk, stopStreaming, targetSampleRate]
  );

  return {
    isStreaming,
    isMuted,
    rmsVolume,
    debugInfo,
    startStreaming,
    stopStreaming,
    toggleMute,
    startSimulation,
    analyser: audioCaptureRef.current?.getAnalyser() || null,
  };
}
