// AudioWorkletProcessor to capture raw Float32 PCM
class RawAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (input && input.length > 0) {
      const channelData = input[0]; // Mono
      
      // We need to copy the data because the underlying array buffer 
      // will be neutered/reused by the browser immediately after this tick.
      const buffer = new Float32Array(channelData.length);
      buffer.set(channelData);
      
      this.port.postMessage(buffer, [buffer.buffer]);
    }
    return true;
  }
}

registerProcessor('raw-audio-processor', RawAudioProcessor);
