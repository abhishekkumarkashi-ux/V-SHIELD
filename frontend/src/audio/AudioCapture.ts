/**
 * Real-Time Audio Capture & 16kHz Resampling Engine for V-SHIELD (SIH 2026).
 * Handles:
 * 1. Mono channel capture from navigator.mediaDevices.getUserMedia
 * 2. High-precision linear interpolation resampling to exact 16000 Hz target
 * 3. AudioWorklet with seamless ScriptProcessor fallback
 * 4. Raw Float32 PCM streaming via ArrayBuffer (no base64, no JSON wrapper)
 * 5. Audio telemetry and pipeline debug metrics
 */

import { VSHIELD_WORKLET_PROCESSOR_NAME, createWorkletModuleUrl } from './audio-worklet';

export interface AudioDebugInfo {
  inputSampleRate: number;
  targetSampleRate: number;
  channelCount: number;
  chunkSamples: number;
  chunkDurationMs: number;
  rmsVolume: number;
  isWorklet: boolean;
  microphoneStatus: 'IDLE' | 'REQUESTING' | 'ACTIVE' | 'MICROPHONE_PERMISSION_REQUIRED' | 'ERROR';
  chunksSent: number;
  bytesSent: number;
}

export interface AudioCaptureOptions {
  targetSampleRate?: number;
  chunkSamples?: number;
  onAudioChunk: (pcmFloat32: ArrayBuffer, debug: AudioDebugInfo) => void;
  onVolumeChange?: (rms: number) => void;
}

/**
 * Resamples a 1D Float32Array from fromRate to toRate using linear interpolation.
 */
export function resampleFloat32Audio(
  input: Float32Array,
  fromRate: number,
  toRate: number
): Float32Array {
  if (fromRate === toRate || input.length === 0) {
    return input;
  }

  const ratio = fromRate / toRate;
  const targetLength = Math.round(input.length / ratio);
  const output = new Float32Array(targetLength);

  for (let i = 0; i < targetLength; i++) {
    const srcIndex = i * ratio;
    const floorIndex = Math.floor(srcIndex);
    const frac = srcIndex - floorIndex;
    const nextIndex = Math.min(floorIndex + 1, input.length - 1);
    output[i] = input[floorIndex] * (1 - frac) + input[nextIndex] * frac;
  }

  return output;
}

export class AudioCapture {
  private targetSampleRate: number;
  private chunkSamples: number;
  private onAudioChunk: (pcmFloat32: ArrayBuffer, debug: AudioDebugInfo) => void;
  private onVolumeChange?: (rms: number) => void;

  private audioCtx: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private analyserNode: AnalyserNode | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private scriptProcessorNode: ScriptProcessorNode | null = null;

  private isRunning: boolean = false;
  private isWorkletActive: boolean = false;
  private resampleBuffer: Float32Array = new Float32Array(0);
  private chunksSent: number = 0;
  private bytesSent: number = 0;
  private microphoneStatus:
    | 'IDLE'
    | 'REQUESTING'
    | 'ACTIVE'
    | 'MICROPHONE_PERMISSION_REQUIRED'
    | 'ERROR' = 'IDLE';

  constructor(options: AudioCaptureOptions) {
    this.targetSampleRate = options.targetSampleRate || 16000;
    this.chunkSamples = options.chunkSamples || 2048;
    this.onAudioChunk = options.onAudioChunk;
    this.onVolumeChange = options.onVolumeChange;
  }

  public async start(): Promise<AudioDebugInfo> {
    if (this.isRunning) {
      return this.getDebugInfo(0);
    }

    this.microphoneStatus = 'REQUESTING';
    let stream: MediaStream;
    try {
      // 1. Request microphone access (mono, standard voice constraints)
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: false,
          autoGainControl: true,
        },
      });
      this.mediaStream = stream;
      this.microphoneStatus = 'ACTIVE';
    } catch (err: any) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        this.microphoneStatus = 'MICROPHONE_PERMISSION_REQUIRED';
      } else {
        this.microphoneStatus = 'ERROR';
      }
      throw err;
    }

    // 2. Initialize AudioContext (let browser select native hardware rate to avoid clock drift)
    const AudioContextClass =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const audioCtx = new AudioContextClass();
    this.audioCtx = audioCtx;

    if (audioCtx.state === 'suspended') {
      await audioCtx.resume();
    }

    const source = audioCtx.createMediaStreamSource(stream);
    this.sourceNode = source;

    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.3;
    this.analyserNode = analyser;
    source.connect(analyser);

    // 3. Attempt AudioWorklet setup
    let workletSuccess = false;
    try {
      if (audioCtx.audioWorklet) {
        const moduleUrl = createWorkletModuleUrl();
        await audioCtx.audioWorklet.addModule(moduleUrl);
        URL.revokeObjectURL(moduleUrl);

        const worklet = new AudioWorkletNode(audioCtx, VSHIELD_WORKLET_PROCESSOR_NAME);
        worklet.port.onmessage = (event) => {
          if (event.data?.type === 'audio_chunk' && event.data.samples) {
            this.handleRawSamples(event.data.samples);
          }
        };

        analyser.connect(worklet);
        // Connect to dummy destination to keep processor running without audio playback
        const silenceGain = audioCtx.createGain();
        silenceGain.gain.value = 0.0;
        worklet.connect(silenceGain);
        silenceGain.connect(audioCtx.destination);

        this.workletNode = worklet;
        this.isWorkletActive = true;
        workletSuccess = true;
      }
    } catch (workletErr) {
      console.warn('[AudioCapture] AudioWorklet initialization failed, falling back to ScriptProcessor:', workletErr);
    }

    // 4. Fallback: ScriptProcessorNode if AudioWorklet unavailable
    if (!workletSuccess) {
      const processor = audioCtx.createScriptProcessor(2048, 1, 1);
      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        this.handleRawSamples(inputData);
      };

      analyser.connect(processor);
      const silenceGain = audioCtx.createGain();
      silenceGain.gain.value = 0.0;
      processor.connect(silenceGain);
      silenceGain.connect(audioCtx.destination);

      this.scriptProcessorNode = processor;
      this.isWorkletActive = false;
    }

    this.isRunning = true;
    return this.getDebugInfo(0);
  }

  private handleRawSamples(rawInput: Float32Array): void {
    if (!this.isRunning || !this.audioCtx) return;

    const inputRate = this.audioCtx.sampleRate;
    // 1. Resample from hardware rate to exactly 16 kHz
    const resampled = resampleFloat32Audio(rawInput, inputRate, this.targetSampleRate);

    // 2. Accumulate in streaming buffer
    const combined = new Float32Array(this.resampleBuffer.length + resampled.length);
    combined.set(this.resampleBuffer, 0);
    combined.set(resampled, this.resampleBuffer.length);
    this.resampleBuffer = combined;

    // 3. Emit bounded chunks of exactly chunkSamples
    while (this.resampleBuffer.length >= this.chunkSamples) {
      const chunk = this.resampleBuffer.slice(0, this.chunkSamples);
      this.resampleBuffer = this.resampleBuffer.slice(this.chunkSamples);

      // Compute RMS energy on Float32
      let sumSq = 0;
      for (let i = 0; i < chunk.length; i++) {
        sumSq += chunk[i] * chunk[i];
      }
      const rms = Math.sqrt(sumSq / chunk.length);

      this.onVolumeChange?.(rms);
      this.chunksSent += 1;
      this.bytesSent += chunk.buffer.byteLength;

      const debug = this.getDebugInfo(rms);
      // Emit raw Float32Array buffer
      this.onAudioChunk(chunk.buffer, debug);
    }
  }

  public getDebugInfo(currentRms = 0): AudioDebugInfo {
    const inputRate = this.audioCtx ? this.audioCtx.sampleRate : 48000;
    return {
      inputSampleRate: inputRate,
      targetSampleRate: this.targetSampleRate,
      channelCount: 1,
      chunkSamples: this.chunkSamples,
      chunkDurationMs: Math.round((this.chunkSamples / this.targetSampleRate) * 1000),
      rmsVolume: currentRms,
      isWorklet: this.isWorkletActive,
      microphoneStatus: this.microphoneStatus,
      chunksSent: this.chunksSent,
      bytesSent: this.bytesSent,
    };
  }

  public stop(): void {
    this.isRunning = false;
    this.microphoneStatus = 'IDLE';
    this.resampleBuffer = new Float32Array(0);

    if (this.workletNode) {
      this.workletNode.disconnect();
      this.workletNode = null;
    }

    if (this.scriptProcessorNode) {
      this.scriptProcessorNode.disconnect();
      this.scriptProcessorNode = null;
    }

    if (this.analyserNode) {
      this.analyserNode.disconnect();
      this.analyserNode = null;
    }

    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    if (this.audioCtx && this.audioCtx.state !== 'closed') {
      this.audioCtx.close();
      this.audioCtx = null;
    }
  }

  public getAnalyser(): AnalyserNode | null {
    return this.analyserNode;
  }
}
