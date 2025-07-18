import os
import io
import time
from typing import Generator, Tuple, List, Optional
import logging
import pyaudio
import wave
import threading
import sherpa_onnx
import numpy as np
import soundfile as sf
import sounddevice as sd

from distiller_cm5_sdk.hardware.audio.audio import Audio
from distiller_cm5_sdk import get_model_path

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class Parakeet:
    def __init__(self, model_config=None, audio_config=None, vad_silence_duration:float=1.0) -> None:
        # override mic gain 
        Audio.set_mic_gain_static(85)
        if audio_config is None:
            audio_config = dict()
        if model_config is None:
            model_config = dict()
        model_path = get_model_path("parakeet")
        self.model_config = {
            "model_path": model_config.get("model_path", model_path),
            "device": model_config.get("device", "cpu"),
            "num_threads": model_config.get("num_threads",4),
            "vad_silence_duration": vad_silence_duration,
        }

        self.audio_config = {
            "channels": audio_config.get("channels", 1),
            "rate": audio_config.get("rate", 16000),
            "chunk": audio_config.get("chunk", 512),
            "record_secs": audio_config.get("record_secs", 3),
            "device": audio_config.get("device", None),  # None means default device
            "format": audio_config.get("format", pyaudio.paInt16)
        }

        # load parakeet asr model
        self.recognizer = self.load_model()

        # load silero vad model
        self.vad_windows_size = None
        self.vad_model = None

        self._is_recording = False
        self._audio_frames = []
        self._audio_thread = None
        self._pyaudio = None
        self._stream = None

    def load_vad_model(self):
        logging.info(f"Loading VAD Model from {self.model_config['model_path']}")
        required_files = ["silero_vad.onnx"]
        missing_files = [_ for _ in required_files if
                         not os.path.isfile(os.path.join(self.model_config["model_path"], _))]

        if missing_files:
            logging.warning(f"Vad Model is incomplete or missing. Missing files: {', '.join(missing_files)}")
            return None

        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = os.path.join(self.model_config["model_path"], "silero_vad.onnx")
        config.silero_vad.min_silence_duration = self.model_config["vad_silence_duration"]
        config.sample_rate = self.audio_config["rate"]

        vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=100)
        if vad is not None:
            logging.info("VAD Model is ready")
            self.vad_windows_size = config.silero_vad.window_size
            return vad
        else:
            logging.error("VAD Model is not ready")
            return None
            
    def load_model(self):
        logging.info(f"Loading Parakeet Model from {self.model_config['model_path']}")

        required_files = ["encoder.onnx", "decoder.onnx", "joiner.onnx", "tokens.txt"]
        missing_files = [f for f in required_files if
                         not os.path.isfile(os.path.join(self.model_config["model_path"], f))]

        if missing_files:
            logging.error(f"Parakeet Model is incomplete or missing. Missing files: {', '.join(missing_files)}")
            raise ValueError(
                f"Parakeet Model loading failed.\n"
                f"Missing files: {', '.join(missing_files)}\n"
                f"Please ensure all required model files are present in the directory: {self.model_config['model_path']}\n"
                f"Expected files: encoder.onnx, decoder.onnx, joiner.onnx, tokens.txt"
            )
        start_time = time.time()
        with suppress_stdout_stderr():
            recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                encoder=os.path.join(self.model_config['model_path'],'encoder.onnx'),
                decoder=os.path.join(self.model_config['model_path'],'decoder.onnx'),
                tokens=os.path.join(self.model_config['model_path'],'tokens.txt'),
                joiner=os.path.join(self.model_config['model_path'],'joiner.onnx'),
                num_threads=1,
                model_type="nemo_transducer"
            )

        if recognizer is None:
            logging.error("Load ParakeetAsr Model error")
            raise ValueError("Load ParakeetAsr Model error")
        end_time = time.time()
        logging.info(f"Loaded ParakeetAsr Model in {end_time - start_time:.2f} s")
        return recognizer

    def transcribe(self, audio_path: str = None) -> Generator[str, None, None]:
        wave, sample_rate = sf.read(audio_path)
        assert sample_rate == 16000, "Audio must be 16kHz"
        assert wave.ndim == 1, "Audio must be mono"

        s = self.recognizer.create_stream()
        s.accept_waveform(sample_rate, wave)
        self.recognizer.decode_stream(s)
        result = s.result.text.strip()

        logging.info(f"Transcribed audio from '{audio_path}' (sample rate: {sample_rate} Hz): '{result}'")

        yield result

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

        s = self.recognizer.create_stream()
        # Read waveform from buffer
        wave, sample_rate = sf.read(buffer)
        assert sample_rate == self.audio_config["rate"], f"Expected sample rate {self.audio_config['rate']}, got {sample_rate}"
        assert wave.ndim == 1, "Audio must be mono for transcribe_buffer"

        s.accept_waveform(self.audio_config["rate"], wave)
        self.recognizer.decode_stream(s)
        result = s.result.text.strip()
        logging.info(f"Transcribed audio from buffer (sample rate: {self.audio_config['rate']} Hz): '{result}'")
        yield result

    def _init_audio(self):
        """Initialize PyAudio instance and get device info if needed"""
        if self._pyaudio is None:
            self._pyaudio = pyaudio.PyAudio()
            
        # Check if any input devices are available
        input_devices = []
        for i in range(self._pyaudio.get_device_count()):
            device_info = self._pyaudio.get_device_info_by_index(i)
            if device_info["maxInputChannels"] > 0:
                input_devices.append((i, device_info["name"]))
                
        if not input_devices:
            raise Exception("No audio input devices found. Please ensure a microphone is connected.")
            
        logging.info(f"Found {len(input_devices)} input device(s): {[name for _, name in input_devices]}")
            
        # If a specific device name was provided, find its index
        if isinstance(self.audio_config["device"], str):
            device_index = None
            for i, name in input_devices:
                if self.audio_config["device"] in name:
                    device_index = i
                    break
            if device_index is None:
                logging.warning(f"Device '{self.audio_config['device']}' not found, using default")
                self.audio_config["device"] = None
            else:
                self.audio_config["device"] = device_index
                logging.info(f"Using specified device: {self.audio_config['device']}")
        else:
            # Use first available input device if no default is available
            try:
                default_info = self._pyaudio.get_default_input_device_info()
                logging.info(f"Using default input device: {default_info['name']}")
            except OSError:
                self.audio_config["device"] = input_devices[0][0]
                logging.info(f"No default device, using first available: {input_devices[0][1]}")
                
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

    def auto_record_and_transcribe(self) -> Generator[str, None, None]:
        """
        Automatic speech recognition with voice activity detection.

        This method continuously monitors audio input, automatically detecting
        speech segments and transcribing them to text. It uses VAD (Voice Activity
        Detection) to identify when speech begins and ends.

        Yields:
            str: Transcribed text segments as they are recognized.

        Raises:
            Exception: If there are issues with audio recording or transcription.
        """
        logging.info("Starting automatic speech recognition with VAD")

        devices = sd.query_devices()
        if len(devices) == 0:
            logging.error("No microphone devices found")
            return

        default_input_device_idx = sd.default.device[0]
        logging.info(f'Use default device: {devices[default_input_device_idx]["name"]}')

        logging.info(f"Audio stream opened with rate: {self.audio_config['rate']}, "
                     f"device: {self.audio_config['device']}")

        # Load VAD model if not already loaded
        if self.vad_model is None:
            self.vad_model = self.load_vad_model()
            if self.vad_model is None:
                logging.error("Failed to load VAD model. Cannot proceed with auto_record_and_transcribe.")
                return

        _buffer = []
        with sd.InputStream(channels=1, dtype="float32", samplerate=self.audio_config["rate"]) as s:
            while True:
                _samples, _ = s.read(int(0.1 * self.audio_config['rate']))
                _samples = _samples.reshape(-1)

                _buffer = np.concatenate([_buffer, _samples])

                while len(_buffer) > self.vad_windows_size:
                    self.vad_model.accept_waveform(_buffer[:self.vad_windows_size])
                    _buffer = _buffer[self.vad_windows_size:]

                while not self.vad_model.empty():
                    _stream = self.recognizer.create_stream()
                    _stream.accept_waveform(self.audio_config["rate"], self.vad_model.front.samples)

                    self.vad_model.pop()
                    self.recognizer.decode_stream(_stream)

                    yield _stream.result.text.strip()


class suppress_stdout_stderr(object):
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
    # Example usage with auto push-to-talk
    try:
        parakeet = Parakeet(vad_silence_duration=0.5)
        print("=== Push-to-Talk Demo ===")
        try:
            input("Press Enter to start recording...")
            if not parakeet.start_recording():
                print("Failed to start recording. Please check audio device availability.")
                exit(1)

            input("Recording... Press Enter to stop...")
            audio_data = parakeet.stop_recording()

            if audio_data:
                # Save the recording to /tmp for debugging (avoids permission issues)
                import tempfile
                try:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        output_filename = f.name
                        f.write(audio_data)
                    logging.info(f"Recording saved to {output_filename}")
                except Exception as e:
                    logging.warning(f"Could not save debug recording: {e}")
                    
                print("Transcribing...")
                for text in parakeet.transcribe_buffer(audio_data):
                    print(f"Transcribed: {text}")
            else:
                print("No audio recorded")
        finally:
            parakeet.cleanup()
    except Exception as e:
        logging.error(f"Failed to initialize Parakeet: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure a microphone is connected and recognized by the system")
        print("2. Check audio permissions: 'sudo usermod -a -G audio $USER'")
        print("3. Test audio capture: 'arecord -l' should show capture devices")
        print("4. Try running with sudo if permission issues persist")
        exit(1)
        
    # for text in parakeet.auto_record_and_transcribe():
    #     print(f"Transcribed: {text}")

