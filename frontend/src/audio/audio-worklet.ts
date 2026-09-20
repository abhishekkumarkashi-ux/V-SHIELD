/**
 * AudioWorklet Processor for V-SHIELD Real-Time Audio Streaming (SIH 2026).
 * Captures raw Float32 audio samples directly on the dedicated audio rendering thread
 * without UI thread jitter or garbage collection stalls.
 */

export const VSHIELD_WORKLET_PROCESSOR_NAME = 'vshield-audio-streamer';

export const audioWorkletCode = `
class VShieldAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    // Bounded chunk size: 2048 samples per chunk
    this.bufferSize = 2048;
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0] || input[0].length === 0) {
      return true;
    }

    const inputChannel = input[0];
    for (let i = 0; i < inputChannel.length; i++) {
      this.buffer[this.bufferIndex++] = inputChannel[i];
      if (this.bufferIndex >= this.bufferSize) {
        // Send a direct Float32Array copy to the main thread
        this.port.postMessage({
          type: 'audio_chunk',
          samples: this.buffer.slice(0)
        });
        this.bufferIndex = 0;
      }
    }

    return true;
  }
}

registerProcessor('${VSHIELD_WORKLET_PROCESSOR_NAME}', VShieldAudioProcessor);
`;

/**
 * Creates an object URL for the AudioWorklet script to load seamlessly
 * across all bundlers without requiring external asset HTTP requests.
 */
export function createWorkletModuleUrl(): string {
  const blob = new Blob([audioWorkletCode], { type: 'application/javascript' });
  return URL.createObjectURL(blob);
}
