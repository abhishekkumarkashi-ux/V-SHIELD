export class AudioRecorder {
  private context: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private processor: AudioWorkletNode | null = null;
  
  private sampleRate = 16000;
  private windowSeconds = 3.0;
  private stepSeconds = 1.5;
  
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
    this.processor = new AudioWorkletNode(this.context, 'raw-audio-processor');
    
    this.processor.port.onmessage = (e) => {
      const data: Float32Array = e.data;
      this.handleAudioData(data);
    };
    
    source.connect(this.processor);
    // Don't connect to destination to prevent feedback loop
    // this.processor.connect(this.context.destination);
  }
  
  private handleAudioData(data: Float32Array) {
    // Append data to buffer
    for (let i = 0; i < data.length; i++) {
      if (this.bufferIndex < this.windowSize) {
        this.buffer[this.bufferIndex++] = data[i];
      }
      
      if (this.bufferIndex === this.windowSize) {
        // Window is full, trigger callback
        const chunkToEmit = new Float32Array(this.buffer);
        this.onChunkReady(chunkToEmit);
        
        // Shift buffer by stepSize for overlapping window
        const overlapSize = this.windowSize - this.stepSize;
        const newBuffer = new Float32Array(this.windowSize);
        newBuffer.set(this.buffer.subarray(this.stepSize));
        this.buffer = newBuffer;
        this.bufferIndex = overlapSize;
      }
    }
  }
  
  stop() {
    if (this.processor) {
      this.processor.disconnect();
    }
    if (this.context) {
      this.context.close();
    }
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
    }
    this.bufferIndex = 0;
  }
}
