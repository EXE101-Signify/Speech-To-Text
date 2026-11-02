class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super(); this.buffer = new Int16Array(2048); this.offset = 0; this.stopped = false;
    this.port.onmessage = () => {
      this.stopped = true;
      if (this.offset) this.port.postMessage(this.buffer.slice(0, this.offset).buffer);
      this.port.postMessage('flushed');
    };
  }
  process(inputs) {
    if (this.stopped) return true;
    const input = inputs[0]?.[0];
    if (input) {
      for (let i = 0; i < input.length; i++) {
        const v = Math.max(-1, Math.min(1, input[i]));
        this.buffer[this.offset++] = v < 0 ? v * 32768 : v * 32767;
        if (this.offset === this.buffer.length) {
          this.port.postMessage(this.buffer.buffer, [this.buffer.buffer]);
          this.buffer = new Int16Array(2048);
          this.offset = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor("pcm-processor", PCMProcessor);
