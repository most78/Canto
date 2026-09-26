"""Captura acotada: el callback nunca hace análisis ni toca la interfaz."""
from queue import Empty, Full, Queue

import sounddevice as sd


class Microphone:
    def __init__(self):
        self.frames = Queue(maxsize=2)
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

    def _callback(self, data, frames, time, status):
        if status:
            self.status = str(status)
        try:
            self.frames.put_nowait(data[:, 0].copy())
        except Full:
            pass

    def latest(self):
        frame = None
        while True:
            try:
                frame = self.frames.get_nowait()
            except Empty:
                return frame

    def stop(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.latest()
