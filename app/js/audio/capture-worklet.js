// AudioWorklet de captura: el hilo de audio sólo copia muestras, nunca analiza.
// Agrupa bloques de `hop` muestras y los envía con la marca de tiempo (reloj
// del AudioContext) del FINAL del bloque, igual que el callback de Python.

class CantoCapture extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.hop = options.processorOptions.hop;
    this.buffer = new Float32Array(this.hop);
    this.filled = 0;
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (!channel) return true;
    let offset = 0;
    while (offset < channel.length) {
      const take = Math.min(this.hop - this.filled, channel.length - offset);
      this.buffer.set(channel.subarray(offset, offset + take), this.filled);
      this.filled += take;
      offset += take;
      if (this.filled === this.hop) {
        const end = currentTime + offset / sampleRate;
        this.port.postMessage({ samples: this.buffer, end }, [this.buffer.buffer]);
        this.buffer = new Float32Array(this.hop);
        this.filled = 0;
      }
    }
    return true;
  }
}

registerProcessor('canto-capture', CantoCapture);
