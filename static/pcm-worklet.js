/**
 * pcm-worklet.js — AudioWorklet processor for 16 kHz mono PCM capture.
 * Loaded by toggleSpeech() in app.js via AudioWorkletNode.
 * Must be served as a static file (blob: URL loading is unreliable).
 */
class PCMCapture extends AudioWorkletProcessor {
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) this.port.postMessage(ch.slice());
    return true;
  }
}
registerProcessor("pcm-capture", PCMCapture);
