import logging
import os
import shutil
import struct
import subprocess
import wave

logger = logging.getLogger("rain_logger")

try:
    import simpleaudio
except ImportError:
    simpleaudio = None


class SoundPlayer:
    def __init__(self, path, enabled=True, volume=1.0, command="aplay"):
        self.path = path
        self.enabled = enabled
        self.volume = max(0.0, min(1.0, volume))
        self.command = command
        self._warned = False

    def play(self):
        if not self.enabled:
            return
        if not self.path or not os.path.exists(self.path):
            if not self._warned:
                logger.warning("Shutter sound file not found: %s", self.path)
                self._warned = True
            return
        try:
            if simpleaudio is not None:
                self._play_simpleaudio()
            else:
                self._play_subprocess()
        except Exception as exc:
            logger.warning("Failed to play shutter sound: %s", exc)

    def _play_simpleaudio(self):
        with wave.open(self.path, "rb") as wav:
            nchannels = wav.getnchannels()
            sampwidth = wav.getsampwidth()
            rate = wav.getframerate()
            data = wav.readframes(wav.getnframes())
        data = self._scale(data, sampwidth)
        obj = simpleaudio.play_buffer(data, nchannels, sampwidth, rate)
        obj.wait_done()

    def _play_subprocess(self):
        command = shutil.which(self.command) or "aplay"
        subprocess.run([command, "-q", self.path], check=False)

    def _scale(self, data, sampwidth):
        if self.volume >= 1.0 or sampwidth != 2:
            return data
        count = len(data) // 2
        values = struct.unpack(f"<{count}h", data)
        scaled = [max(-32768, min(32767, int(v * self.volume))) for v in values]
        return struct.pack(f"<{count}h", *scaled)
