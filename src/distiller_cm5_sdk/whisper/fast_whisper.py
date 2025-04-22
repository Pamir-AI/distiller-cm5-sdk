import os
import io
import logging
import threading
import time
import wave
from contextlib import contextmanager
from typing import Generator, List, Optional, Dict

import numpy as np  # noqa: F401  # imported for completeness (faster‑whisper depends on np)
import pyaudio
from faster_whisper import WhisperModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


@contextmanager
def suppress_stdout_stderr():
    """Silence CTranslate2 / Faster‑Whisper verbose output while loading the model."""
    null_fds = [os.open(os.devnull, os.O_RDWR) for _ in range(2)]
    saved_fds = (os.dup(1), os.dup(2))
    try:
        os.dup2(null_fds[0], 1)
        os.dup2(null_fds[1], 2)
        yield
    finally:
        os.dup2(saved_fds[0], 1)
        os.dup2(saved_fds[1], 2)
        os.close(null_fds[0])
        os.close(null_fds[1])


class Whisper:
    """Push‑to‑talk recorder + Faster‑Whisper wrapper with safe thread cleanup."""

    # ---------------------------------------------------------------------
    def __init__(self, model_config: Optional[Dict] = None, audio_config: Optional[Dict] = None):
        model_config = model_config or {}
        audio_config = audio_config or {}

        model_dir = model_config.get("model_hub_path", os.path.join(os.path.dirname(__file__), "models"))
        model_size = model_config.get("model_size", "faster-distil-whisper-small.en")

        # --- whisper params
        self.model_config = {
            "model_size_or_path": os.path.join(model_dir, model_size),
            "device": model_config.get("device", "cpu"),
            "compute_type": model_config.get("compute_type", "int8"),
            "beam_size": model_config.get("beam_size", 5),
            "language": model_config.get("language", "en"),
        }

        # --- audio params
        self.audio_config: Dict = {
            "channels": audio_config.get("channels", 1),
            "rate": audio_config.get("rate", 48_000),
            "chunk": audio_config.get("chunk", 1024),
            "record_secs": audio_config.get("record_secs", 3),
            "device": audio_config.get("device", None),  # str device name or int index or None
            "format": audio_config.get("format", pyaudio.paInt16),
        }

        # runtime members
        self._pyaudio: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None
        self._audio_frames: List[bytes] = []
        self._record_thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._is_recording = False

        self.model = self._load_model()

    # ------------------------------------------------------------------ MODEL
    def _load_model(self):
        model_path = self.model_config["model_size_or_path"]
        if not os.path.isfile(os.path.join(model_path, "model.bin")):
            raise FileNotFoundError(f"Whisper model not found in {model_path}")

        logging.info(f"Loading Whisper from {model_path}")
        with suppress_stdout_stderr():
            model = WhisperModel(
                model_size_or_path=model_path,
                device=self.model_config["device"],
                compute_type=self.model_config["compute_type"],
            )
        return model

    # ---------------------------------------------------------------- AUDIO INIT
    def _ensure_pyaudio(self):
        if self._pyaudio is None:
            self._pyaudio = pyaudio.PyAudio()
        # resolve device name → index
        if isinstance(self.audio_config["device"], str):
            wanted = self.audio_config["device"].lower()
            for idx in range(self._pyaudio.get_device_count()):
                info = self._pyaudio.get_device_info_by_index(idx)
                if wanted in info["name"].lower():
                    self.audio_config["device"] = idx
                    break
            else:
                logging.warning(f"Audio device '{wanted}' not found; falling back to default")
                self.audio_config["device"] = None

    # ---------------------------------------------------------------- RECORD THREAD
    def _record_loop(self):
        try:
            while not self._stop_evt.is_set():
                try:
                    data = self._stream.read(self.audio_config["chunk"], exception_on_overflow=False)
                    if data:
                        self._audio_frames.append(data)
                except IOError as e:
                    if e.errno == pyaudio.paInputOverflowed:
                        logging.warning("Input overflow; frame dropped.")
                    else:
                        logging.error(f"PyAudio IOError: {e}")
                        break
        finally:
            # always clean up stream INSIDE the thread to avoid races
            if self._stream:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                finally:
                    self._stream = None
            logging.info("Record thread exiting cleanly")

    # ---------------------------------------------------------------- START / STOP
    def start_recording(self) -> bool:
        if self._is_recording:
            logging.warning("Recording already in progress")
            return False

        try:
            self._ensure_pyaudio()
            self._stream = self._pyaudio.open(
                format=self.audio_config["format"],
                channels=self.audio_config["channels"],
                rate=self.audio_config["rate"],
                input=True,
                input_device_index=self.audio_config["device"],
                frames_per_buffer=self.audio_config["chunk"],
            )
        except Exception as exc:
            logging.error(f"Failed to open audio stream: {exc}")
            return False

        self._audio_frames.clear()
        self._stop_evt.clear()
        self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._record_thread.start()
        self._is_recording = True
        logging.info("Recording started")
        return True

    def stop_recording(self) -> Optional[bytes]:
        if not self._is_recording:
            logging.warning("stop_recording called but we are not recording")
            return None

        logging.info("Signalling record thread to stop …")
        self._stop_evt.set()
        if self._record_thread:
            self._record_thread.join(timeout=2.0)
            self._record_thread = None

        self._is_recording = False

        if not self._audio_frames:
            logging.warning("No audio captured")
            return None

        # build a WAV in‑memory
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(self.audio_config["channels"])
            wf.setsampwidth(self._pyaudio.get_sample_size(self.audio_config["format"]))
            wf.setframerate(self.audio_config["rate"])
            wf.writeframes(b"".join(self._audio_frames))
        return buffer.getvalue()

    # ---------------------------------------------------------------- TRANSCRIBE
    def _do_transcribe(self, source) -> Generator[str, None, None]:
        segments, info = self.model.transcribe(
            source,
            beam_size=self.model_config["beam_size"],
            language=self.model_config["language"],
        )
        logging.info(f"Detected language '{info.language}' (p={info.language_probability:.2%})")
        for seg in segments:
            logging.info("[%.2fs → %.2fs] %s", seg.start, seg.end, seg.text)
            yield seg.text

    def transcribe_file(self, path: str) -> Generator[str, None, None]:
        return self._do_transcribe(path)

    def transcribe_buffer(self, wav_bytes: bytes) -> Generator[str, None, None]:
        return self._do_transcribe(io.BytesIO(wav_bytes))

    # ---------------------------------------------------------------- CLEANUP
    def cleanup(self):
        if self._is_recording:
            self.stop_recording()
        if self._pyaudio:
            self._pyaudio.terminate()
            self._pyaudio = None


# ---------------------------------------------------------------------- DEMO
if __name__ == "__main__":
    rec = WhisperRecorder(model_config={"model_size": "faster-distil-whisper-small.en"})

    try:
        input("Press Enter to start recording …")
        if not rec.start_recording():
            raise SystemExit

        input("Recording … press Enter to stop …")
        wav = rec.stop_recording()
        if not wav:
            raise SystemExit("Nothing captured")

        with open("debug_recording.wav", "wb") as f:
            f.write(wav)
        logging.info("Saved debug_recording.wav")

        print("Transcribing …")
        for txt in rec.transcribe_buffer(wav):
            print("→", txt)
    finally:
        rec.cleanup()
