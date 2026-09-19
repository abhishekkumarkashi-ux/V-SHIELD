import { useState, useRef, useCallback } from 'react';

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

  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const simulationIntervalRef = useRef<number | null>(null);

  // Converts Float32 [-1.0, 1.0] array into 16-bit linear PCM Int16Array
  const convertFloat32ToPCM16 = (input: Float32Array): ArrayBuffer => {
    const output = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i]));
      output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return output.buffer;
  };

  const startStreaming = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: targetSampleRate,
          echoCancellation: true,
          noiseSuppression: false,
          autoGainControl: true,
        },
      });

      mediaStreamRef.current = stream;

      const audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)({
        sampleRate: targetSampleRate,
      });
      audioContextRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;

      // ScriptProcessor chunking (2048 samples @ 16kHz is ~128ms)
      const processor = audioCtx.createScriptProcessor(2048, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);

        // Compute RMS
        let sum = 0;
        for (let i = 0; i < inputData.length; i++) {
          sum += inputData[i] * inputData[i];
        }
        const rms = Math.sqrt(sum / inputData.length);
        setRmsVolume(rms);

        const pcmBuffer = convertFloat32ToPCM16(inputData);
        onAudioChunk(pcmBuffer);
      };

      source.connect(analyser);
      analyser.connect(processor);
      processor.connect(audioCtx.destination);

      setIsStreaming(true);
      setIsMuted(false);
    } catch (err) {
      console.error('[AudioStreamer] Microphone access failed:', err);
      throw err;
    }
  }, [onAudioChunk, targetSampleRate]);

  const stopStreaming = useCallback(() => {
    if (simulationIntervalRef.current) {
      clearInterval(simulationIntervalRef.current);
      simulationIntervalRef.current = null;
    }

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (analyserRef.current) {
      analyserRef.current.disconnect();
      analyserRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }

    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    setIsStreaming(false);
    setRmsVolume(0);
  }, []);

  const toggleMute = useCallback(() => {
    if (mediaStreamRef.current) {
      const audioTrack = mediaStreamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        setIsMuted(!audioTrack.enabled);
      }
    }
  }, []);

  // Demo / Simulation mode for testing scenarios without a live microphone
  const startSimulation = useCallback((type: 'genuine' | 'clone' | 'unknown') => {
    stopStreaming();
    setIsStreaming(true);

    const chunkSize = 2048;
    let phase = 0;

    simulationIntervalRef.current = window.setInterval(() => {
      const buffer = new Float32Array(chunkSize);
      for (let i = 0; i < chunkSize; i++) {
        phase += 0.05;
        if (type === 'genuine') {
          // Clean multi-harmonic human speech simulation
          buffer[i] =
            (Math.sin(phase) * 0.4 +
              Math.sin(phase * 2.2) * 0.2 +
              Math.sin(phase * 3.7) * 0.1) *
            (0.5 + 0.5 * Math.sin(phase * 0.05));
        } else if (type === 'clone') {
          // Synthetic vocoder buzzy texture + high frequency robotic artifacts
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
      const pcmBuffer = convertFloat32ToPCM16(buffer);
      onAudioChunk(pcmBuffer);
    }, 128); // Every 128ms
  }, [onAudioChunk, stopStreaming]);

  return {
    isStreaming,
    isMuted,
    rmsVolume,
    startStreaming,
    stopStreaming,
    toggleMute,
    startSimulation,
    analyser: analyserRef.current,
  };
}
