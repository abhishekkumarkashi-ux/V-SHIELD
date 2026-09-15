export class AudioRecorder {
  private context: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private processor: AudioWorkletNode | null = null;
  private analyser: AnalyserNode | null = null;
  
  // Audio streaming protocol settings (aligned with backend AUDIO_PROTOCOL)
  private sampleRate = 16000;
  private windowSeconds = 1.0;
  private stepSeconds = 1.0;
  
  private windowSize: number;
  private stepSize: number;
  
  private buffer: Float32Array;
  private bufferIndex = 0;
  
  private onChunkReady: (chunk: Float32Array) => void;
  
  constructor(onChunkReady: (chunk: Float32Array) => void) {
    this.onChunkReady = onChunkReady;
    this.windowSize = this.sampleRate * this.windowSeconds;
    this.stepSize = this.sampleRate * this.stepSeconds;
    this.buffer = new Float32Array(this.windowSize);
  }
  
  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    this.context = new AudioContext({ sampleRate: this.sampleRate });
    
    await this.context.audioWorklet.addModule('/processor.js');
    
    const source = this.context.createMediaStreamSource(this.stream);
    
    // Real-time AnalyserNode for truthful live waveform visualization
    this.analyser = this.context.createAnalyser();
    this.analyser.fftSize = 64;
    this.analyser.smoothingTimeConstant = 0.8;
    source.connect(this.analyser);
    
    this.processor = new AudioWorkletNode(this.context, 'raw-audio-processor');
    
    this.processor.port.onmessage = (e) => {
      const data: Float32Array = e.data;
      this.handleAudioData(data);
    };
    
    source.connect(this.processor);
    // Do not connect to destination to avoid feedback loops
  }
  
  getAnalyser(): AnalyserNode | null {
    return this.analyser;
  }
  
  private handleAudioData(data: Float32Array) {
    for (let i = 0; i < data.length; i++) {
      if (this.bufferIndex < this.windowSize) {
        this.buffer[this.bufferIndex++] = data[i];
      }
      
      if (this.bufferIndex === this.windowSize) {
        const chunkToEmit = new Float32Array(this.buffer);
        this.onChunkReady(chunkToEmit);
        
        const overlapSize = this.windowSize - this.stepSize;
        const newBuffer = new Float32Array(this.windowSize);
        if (overlapSize > 0) {
          newBuffer.set(this.buffer.subarray(this.stepSize));
        }
        this.buffer = newBuffer;
        this.bufferIndex = overlapSize;
      }
    }
  }
  
  stop() {
    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }
    if (this.analyser) {
      this.analyser.disconnect();
      this.analyser = null;
    }
    if (this.context) {
      this.context.close();
      this.context = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    this.bufferIndex = 0;
  }
}
