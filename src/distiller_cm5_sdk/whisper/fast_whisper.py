import io
import logging
import os
import threading
import wave
from collections.abc import Generator

import pyaudio
from faster_whisper import WhisperModel

from distiller_cm5_sdk import get_model_path
from distiller_cm5_sdk.hardware.audio.audio import Audio

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class Whisper:
    def __init__(self, model_config=None, audio_config=None) -> None:
        # Try to set mic gain if hardware supports it
        if Audio.has_audio_controls():
            logging.info("Setting microphone gain for optimal speech recognition")
            Audio.set_mic_gain_static(85)
        else:
            logging.info("Hardware volume controls not available - using system defaults")

        if audio_config is None:
            audio_config = {}
        if model_config is None:
            model_config = {}
        model_path = get_model_path("whisper")
        self.model_config = {
            "model_hub_path": model_config.get("model_hub_path", model_path),
            "model_size": model_config.get("model_size", "faster-distil-whisper-small.en"),
            "model_size_or_path": os.path.join(
                model_config.get("model_hub_path", model_path),
                model_config.get("model_size", "faster-distil-whisper-small.en")),
            "device": model_config.get("device", "cpu"),
            "compute_type": model_config.get("compute_type", "int8"),
            "beam_size": model_config.get("beam_size", 5),
            "language": model_config.get("language", "en")
        }
        self.audio_config = {
            "channels": audio_config.get("channels", 1),
            "rate": audio_config.get("rate", 48000),
            "chunk": audio_config.get("chunk", 1024),
            "record_secs": audio_config.get("record_secs", 3),
            "device": audio_config.get("device", None),  # None means default device
            "format": audio_config.get("format", pyaudio.paInt16)
        }

        self.model = self.load_model()  # Load models once during initialization
        self._is_recording = False
        self._audio_frames = []
        self._audio_thread = None
        self._pyaudio = None
        self._stream = None

    def load_model(self):
        logging.info(f"Loading Whisper Model from {self.model_config['model_size_or_path']}")
        if not os.path.isfile(os.path.join(self.model_config["model_size_or_path"], "model.bin")):
            logging.error("Model not found")
            raise ValueError(
                f"Whisper Model not found, please put whisper model in {self.model_config['model_size_or_path']}")

        with suppress_stdout_stderr():
            model = WhisperModel(
                model_size_or_path=self.model_config["model_size_or_path"],
                device=self.model_config["device"],
                compute_type=self.model_config["compute_type"]
            )

        if model is None:
            logging.error("Load Whisper Model error")
            raise ValueError("Load Whisper Model error")
        return model

    def transcribe(self, audio_path: str = None) -> Generator[str, None, None]:
        segments, info = self.model.transcribe(
            audio_path,
            beam_size=self.model_config["beam_size"],
            language=self.model_config["language"]
        )

        logging.info(f"Detected language '{info.language}' with probability {info.language_probability}")

        for segment in segments:
            logging.info(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
            yield segment.text

    def transcribe_buffer(self, audio_data: bytes) -> Generator[str, None, None]:
        """
        Transcribe audio from a WAV format byte buffer.

        Args:
            audio_data: Audio data as bytes in WAV format

        Returns:
            Generator yielding transcribed text segments
        """
        # Create in-memory file-like object
        buffer = io.BytesIO(audio_data)

        segments, info = self.model.transcribe(
            buffer,
            beam_size=self.model_config["beam_size"],
            language=self.model_config["language"]
        )

        logging.info(f"Detected language '{info.language}' with probability {info.language_probability}")

        for segment in segments:
            logging.info(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
            yield segment.text

    def _init_audio(self):
        """Initialize PyAudio instance and get device info if needed"""
        if self._pyaudio is None:
            self._pyaudio = pyaudio.PyAudio()

        # If a specific device name was provided, find its index
        if isinstance(self.audio_config["device"], str):
            device_index = None
            for i in range(self._pyaudio.get_device_count()):
                device_info = self._pyaudio.get_device_info_by_index(i)
                if self.audio_config["device"] in device_info["name"]:
                    device_index = i
                    break
            if device_index is None:
                logging.warning(f"Device '{self.audio_config['device']}' not found, using default")
                self.audio_config["device"] = None
            else:
                self.audio_config["device"] = device_index

    def _recording_thread(self):
        """Thread function for audio recording"""
        while self._is_recording:
            try:
                data = self._stream.read(self.audio_config["chunk"])
                self._audio_frames.append(data)
            except Exception as e:
                logging.error(f"Error recording audio: {e}")
                break

    def start_recording(self) -> bool:
        """
        Start recording audio (push-to-talk start).

        Returns:
            True if recording started successfully, False otherwise
        """
        if self._is_recording:
            logging.warning("Already recording")
            return False

        try:
            self._init_audio()

            self._stream = self._pyaudio.open(
                format=self.audio_config["format"],
                channels=self.audio_config["channels"],
                rate=self.audio_config["rate"],
                input=True,
                input_device_index=self.audio_config["device"],
                frames_per_buffer=self.audio_config["chunk"]
            )

            self._audio_frames = []
            self._is_recording = True
            self._audio_thread = threading.Thread(target=self._recording_thread)
            self._audio_thread.daemon = True
            self._audio_thread.start()

            logging.info("Recording started")
            return True
        except Exception as e:
            logging.error(f"Failed to start recording: {e}")
            self._is_recording = False
            return False

    def stop_recording(self) -> bytes:
        """
        Stop recording audio (push-to-talk end) and return the recorded audio as bytes.

        Returns:
            Audio data as bytes in WAV format
        """
        if not self._is_recording:
            logging.warning("Not recording")
            return None

        self._is_recording = False
        if self._audio_thread:
            self._audio_thread.join(timeout=1.0)

        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None

        logging.info("Recording stopped")

        # Convert raw audio data to WAV format
        if not self._audio_frames:
            logging.warning("No audio recorded")
            return None

        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(self.audio_config["channels"])
            wf.setsampwidth(self._pyaudio.get_sample_size(self.audio_config["format"]))
            wf.setframerate(self.audio_config["rate"])
            wf.writeframes(b''.join(self._audio_frames))

        return buffer.getvalue()

    def cleanup(self):
        """Release PyAudio resources"""
        if self._pyaudio:
            self._pyaudio.terminate()
            self._pyaudio = None

    def record_and_transcribe_ptt(self) -> Generator[str, None, None]:
        """
        Simple interactive push-to-talk demo.
        Press Enter to start recording, press Enter again to stop and transcribe.

        Returns:
            Generator yielding transcribed text segments
        """
        try:
            input("Press Enter to start recording...")
            if not self.start_recording():
                return

            input("Recording... Press Enter to stop...")
            audio_data = self.stop_recording()

            if audio_data:
                print("Transcribing...")
                yield from self.transcribe_buffer(audio_data)
            else:
                print("No audio recorded")
        finally:
            self.cleanup()


class suppress_stdout_stderr:
    def __init__(self):
        self.null_fds = [os.open(os.devnull, os.O_RDWR) for x in range(2)]
        self.save_fds = (os.dup(1), os.dup(2))

    def __enter__(self):
        os.dup2(self.null_fds[0], 1)
        os.dup2(self.null_fds[1], 2)

    def __exit__(self, *_):
        os.dup2(self.save_fds[0], 1)
        os.dup2(self.save_fds[1], 2)
        os.close(self.null_fds[0])
        os.close(self.null_fds[1])


if __name__ == '__main__':
    # Example usage with push-to-talk
    whisper = Whisper(model_config={"model_size": "faster-distil-whisper-small.en"})

    print("=== Push-to-Talk Demo ===")
    try:
        input("Press Enter to start recording...")
        if not whisper.start_recording():
            exit()

        input("Recording... Press Enter to stop...")
        audio_data = whisper.stop_recording()

        if audio_data:
            # Save the recording
            output_filename = "debug_recording.wav"
            with open(output_filename, "wb") as f:
                f.write(audio_data)
            logging.info(f"Recording saved to {output_filename}")

            print("Transcribing...")
            for text in whisper.transcribe_buffer(audio_data):
                print(f"Transcribed: {text}")
        else:
            print("No audio recorded")
    finally:
        whisper.cleanup()

    # Transcribe a file
    # for text in whisper.transcribe(audio_path="./test.wav"):
    #     print(f"Transcribed: {text}")
