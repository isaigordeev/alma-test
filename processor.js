// processor.js
class AudioProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0][0]; // first channel
    if (input) {
      // Send the float32 buffer to main thread
      this.port.postMessage(input.buffer, [input.buffer]);
    }
    return true; // keep alive
  }
}

registerProcessor("audio-processor", AudioProcessor);
