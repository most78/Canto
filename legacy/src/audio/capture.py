"""Captura acotada: el callback nunca hace análisis ni toca la interfaz."""
import time
from queue import Empty, Full, Queue

import sounddevice as sd


class Microphone:
    def __init__(self):
        # Unos 1,3 s de margen con bloques de 80 ms: la interfaz los lee todos.
        self.frames = Queue(maxsize=16)
        self.stream = None
        self.sample_rate = 44100
        self.status = ""

    def start(self, device=None):
        self.stop()
        info = sd.query_devices(device, "input")
        self.sample_rate = int(info["default_samplerate"])
        self.status = ""
        self.stream = sd.InputStream(
            device=device, channels=1, samplerate=self.sample_rate,
            blocksize=max(512, round(self.sample_rate * .08)),
            dtype="float32", callback=self._callback,
        )
        try:
            self.stream.start()
        except Exception:
            self.stop()
            raise

    def _callback(self, data, frames, time_info, status):
        if status:
            self.status = str(status)
        try:
            # Marca monotónica de llegada ≈ final del bloque: sirve para puntuar
            # con el tiempo real del audio y no con el ritmo de la interfaz.
            self.frames.put_nowait((time.monotonic(), data[:, 0].copy()))
        except Full:
            pass

    def drain(self):
        """Todos los bloques pendientes, en orden, como (marca, muestras)."""
        items = []
        while True:
            try:
                items.append(self.frames.get_nowait())
            except Empty:
                return items

    def latest(self):
        items = self.drain()
        return items[-1][1] if items else None

    def stop(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.drain()
