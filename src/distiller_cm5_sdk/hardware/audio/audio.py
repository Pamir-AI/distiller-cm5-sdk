#!/usr/bin/env python3
"""
Audio module for CM5 SDK.
Provides functionality for audio recording, playback, and microphone/speaker volume control.
"""

import os
import subprocess
import threading
import time
from collections.abc import Callable
from typing import BinaryIO


class AudioError(Exception):
    """Custom exception for Audio-related errors."""

    pass


class Audio:
    """
    Audio class for interacting with the CM5 audio system.

    This class provides functionality to:
    - Record audio to files
    - Record audio to a stream for real-time use
    - Play audio from files
    - Play audio from streams
    - Adjust microphone volume/gain (Optional)
    - Adjust speaker volume (Optional)
    """

    # Default hardware paths for PamirAI soundcard controls
    MIC_GAIN_PATH = (
        "/sys/devices/platform/axi/1000120000.pcie/1f00074000.i2c/i2c-1/1-0018/input_gain"
    )
    SPEAKER_VOLUME_PATH = (
        "/sys/devices/platform/axi/1000120000.pcie/1f00074000.i2c/i2c-1/1-0018/volume_level"
    )

    @staticmethod
    def is_raspberry_pi() -> bool:
        """Check if the current system is a Raspberry Pi."""
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model") as f:
                    return "raspberry" in f.read().lower()
            elif os.path.exists("/sys/firmware/devicetree/base/model"):
                with open("/sys/firmware/devicetree/base/model") as f:
                    return "raspberry" in f.read().lower()
        except Exception:
            return False
        return False

    @staticmethod
    def has_audio_controls() -> bool:
        """Check if this system has the PamirAI soundcard controls."""
        return os.path.exists(Audio.MIC_GAIN_PATH) and os.path.exists(Audio.SPEAKER_VOLUME_PATH)

    def __init__(
        self,
        sample_rate: int = 48000,
        channels: int = 2,
        format_type: str = "S16_LE",
        input_device: str = "hw:0,0",
        output_device: str = "plughw:0",
        auto_check_config: bool = True,
    ):
        """
        Initialize the Audio object.

        Args:
            sample_rate: Sample rate in Hz
            channels: Number of audio channels (1=mono, 2=stereo)
            format_type: Audio format type (S16_LE, S24_LE, etc.)
            input_device: Audio input device
            output_device: Audio output device
            auto_check_config: Whether to automatically check system configuration

        Raises:
            AudioError: If audio configuration is invalid or audio can't be initialized
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.format_type = format_type
        self.input_device = input_device
        self.output_device = output_device

        # Default microphone gain and speaker volume levels
        self._mic_gain = 50
        self._speaker_volume = 60

        # Check if we're on a system with hardware audio controls
        self._has_hw_controls = Audio.has_audio_controls()

        # Recording state
        self._is_recording = False
        self._record_thread = None
        self._stop_recording = threading.Event()

        # Playback state
        self._is_playing = False
        self._play_thread = None
        self._stop_playback = threading.Event()

        # Thread synchronization
        self._lock = threading.Lock()

        # Check system configuration
        if auto_check_config:
            self.check_system_config()

        # Apply default settings
        if self._has_hw_controls:
            self.set_mic_gain(self._mic_gain)
            self.set_speaker_volume(self._speaker_volume)

    def check_system_config(self) -> bool:
        """
        Check if the system is properly configured for audio use.

        Returns:
            bool: True if configuration is valid

        Raises:
            AudioError: If configuration is invalid
        """
        # Check if arecord and aplay are installed
        try:
            subprocess.run(["arecord", "--version"], capture_output=True, check=False)
        except FileNotFoundError:
            raise AudioError("arecord not found. Please install ALSA utils package.")

        try:
            subprocess.run(["aplay", "--version"], capture_output=True, check=False)
        except FileNotFoundError:
            raise AudioError("aplay not found. Please install ALSA utils package.")

        # Check if input/output paths exist
        if Audio.is_raspberry_pi():
            # Only warn but don't fail if paths don't exist
            if not os.path.exists(Audio.MIC_GAIN_PATH):
                print(f"Warning: Microphone gain control path not found: {Audio.MIC_GAIN_PATH}")
                print("Volume control features will be disabled.")

            if not os.path.exists(Audio.SPEAKER_VOLUME_PATH):
                print(
                    f"Warning: Speaker volume control path not found: {Audio.SPEAKER_VOLUME_PATH}"
                )
                print("Volume control features will be disabled.")

        # List available audio devices
        try:
            result = subprocess.run(["arecord", "-l"], capture_output=True, text=True, check=False)
            if result.returncode != 0 or "no soundcards found" in result.stderr:
                print("Warning: No audio input devices detected. Continuing anyway.")
        except Exception as e:
            print(f"Warning: Error checking audio devices: {str(e)}")

        return True

    def set_mic_gain(self, gain: int) -> None:
        """
        Set the microphone gain/volume.

        Args:
            gain: Gain value (typically 0-100)

        Raises:
            AudioError: If setting the gain fails
        """
        if not self._has_hw_controls:
            self._mic_gain = gain
            return

        self._mic_gain = Audio.set_mic_gain_static(gain)

    @staticmethod
    def set_mic_gain_static(gain: int) -> int:
        """
        Static method to set the microphone gain/volume.

        Args:
            gain: Gain value (typically 0-100)

        Returns:
            int: The set gain value

        Raises:
            AudioError: If setting the gain fails
        """
        if not isinstance(gain, int) or gain < 0:
            raise AudioError(f"Invalid gain value: {gain}. Must be a positive integer.")

        # If we don't have the control file, just return the requested gain
        if not os.path.exists(Audio.MIC_GAIN_PATH):
            return gain

        try:
            # Use sudo to write to the system control file
            cmd = f"echo {gain} | sudo tee {Audio.MIC_GAIN_PATH} > /dev/null"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)

            if result.returncode != 0:
                print(f"Warning: Failed to set microphone gain: {result.stderr}")

            return gain
        except Exception as e:
            print(f"Warning: Error setting microphone gain: {str(e)}")
            return gain

    def get_mic_gain(self) -> int:
        """
        Get the current microphone gain/volume.

        Returns:
            int: Current gain value

        Raises:
            AudioError: If getting the gain fails
        """
        if not self._has_hw_controls:
            return self._mic_gain

        self._mic_gain = Audio.get_mic_gain_static()
        return self._mic_gain

    @staticmethod
    def get_mic_gain_static() -> int:
        """
        Static method to get the current microphone gain/volume.

        Returns:
            int: Current gain value

        Raises:
            AudioError: If getting the gain fails
        """
        # If we don't have the control file, return a default value
        if not os.path.exists(Audio.MIC_GAIN_PATH):
            return 0

        try:
            # Read from the system control file
            result = subprocess.run(
                ["sudo", "cat", Audio.MIC_GAIN_PATH], capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                print(f"Warning: Failed to get microphone gain: {result.stderr}")
                return 0

            # Return the gain value
            return int(result.stdout.strip())

        except Exception as e:
            print(f"Warning: Error getting microphone gain: {str(e)}")
            return 0

    def set_speaker_volume(self, volume: int) -> None:
        """
        Set the speaker volume.

        Args:
            volume: Volume value (typically 0-100)

        Raises:
            AudioError: If setting the volume fails
        """
        if not self._has_hw_controls:
            self._speaker_volume = volume
            return

        self._speaker_volume = Audio.set_speaker_volume_static(volume)

    @staticmethod
    def set_speaker_volume_static(volume: int) -> int:
        """
        Static method to set the speaker volume.

        Args:
            volume: Volume value (typically 0-100)

        Returns:
            int: The set volume value

        Raises:
            AudioError: If setting the volume fails
        """
        if not isinstance(volume, int) or volume < 0:
            raise AudioError(f"Invalid volume value: {volume}. Must be a positive integer.")

        # If we don't have the control file, just return the requested volume
        if not os.path.exists(Audio.SPEAKER_VOLUME_PATH):
            return volume

        try:
            # Use sudo to write to the system control file
            cmd = f"echo {volume} | sudo tee {Audio.SPEAKER_VOLUME_PATH} > /dev/null"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)

            if result.returncode != 0:
                print(f"Warning: Failed to set speaker volume: {result.stderr}")

            return volume
        except Exception as e:
            print(f"Warning: Error setting speaker volume: {str(e)}")
            return volume

    def get_speaker_volume(self) -> int:
        """
        Get the current speaker volume.

        Returns:
            int: Current volume value

        Raises:
            AudioError: If getting the volume fails
        """
        if not self._has_hw_controls:
            return self._speaker_volume

        self._speaker_volume = Audio.get_speaker_volume_static()
        return self._speaker_volume

    @staticmethod
    def get_speaker_volume_static() -> int:
        """
        Static method to get the current speaker volume.

        Returns:
            int: Current volume value

        Raises:
            AudioError: If getting the volume fails
        """
        # If we don't have the control file, return a default value
        if not os.path.exists(Audio.SPEAKER_VOLUME_PATH):
            return 0

        try:
            # Read from the system control file
            result = subprocess.run(
                ["sudo", "cat", Audio.SPEAKER_VOLUME_PATH],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                print(f"Warning: Failed to get speaker volume: {result.stderr}")
                return 0

            # Return the volume value
            return int(result.stdout.strip())

        except Exception as e:
            print(f"Warning: Error getting speaker volume: {str(e)}")
            return 0

    def record(self, filepath: str, duration: float | None = None) -> str:
        """
        Record audio to a file.

        Args:
            filepath: Path to save the recorded audio
            duration: Recording duration in seconds, or None for manual stop

        Returns:
            str: Path to the recorded file

        Raises:
            AudioError: If recording fails
        """
        if self._is_recording:
            raise AudioError("Recording already in progress")

        if duration is not None and not isinstance(duration, int | float):
            raise AudioError(f"Invalid duration: {duration}. Must be a number or None.")

        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        # Build command
        cmd = [
            "arecord",
            "-D",
            self.input_device,
            "-f",
            self.format_type,
            "-r",
            str(self.sample_rate),
            "-c",
            str(self.channels),
        ]

        # Add duration if specified
        if duration is not None:
            cmd.extend(["-d", str(int(duration))])

        # Add output file
        cmd.append(filepath)

        try:
            with self._lock:
                self._is_recording = True
                self._stop_recording.clear()

                if duration is None:
                    # For manual stop, run in a thread
                    def record_thread():
                        proc = subprocess.Popen(cmd)
                        # Wait for stop event
                        while not self._stop_recording.is_set():
                            if proc.poll() is not None:
                                break
                            time.sleep(0.1)
                        # Kill if still running
                        if proc.poll() is None:
                            proc.terminate()
                            proc.wait()

                    self._record_thread = threading.Thread(target=record_thread)
                    self._record_thread.start()
                    return filepath
                else:
                    # For fixed duration, run synchronously
                    subprocess.run(cmd, check=True)
                    self._is_recording = False
                    return filepath

        except Exception as e:
            self._is_recording = False
            self._stop_recording.set()
            raise AudioError(f"Recording failed: {str(e)}")

    def stop_recording(self) -> None:
        """
        Stop an ongoing recording.

        Raises:
            AudioError: If no recording is in progress
        """
        if not self._is_recording:
            raise AudioError("No recording in progress")

        with self._lock:
            self._stop_recording.set()
            if self._record_thread and self._record_thread.is_alive():
                self._record_thread.join(timeout=2)
            self._is_recording = False

    def stream_record(
        self,
        callback: Callable[[bytes], None],
        buffer_size: int = 4096,
        stop_event: threading.Event | None = None,
    ) -> threading.Thread:
        """
        Record audio to a stream for real-time processing.

        Args:
            callback: Function to call with each audio buffer
            buffer_size: Size of audio buffer in bytes
            stop_event: Event to signal when recording should stop

        Returns:
            threading.Thread: The recording thread

        Raises:
            AudioError: If recording fails
        """
        if self._is_recording:
            raise AudioError("Recording already in progress")

        if not callable(callback):
            raise AudioError("Callback must be a callable function")

        # Use provided stop event or create one
        self._stop_recording = stop_event if stop_event is not None else threading.Event()

        # Build command
        cmd = [
            "arecord",
            "-D",
            self.input_device,
            "-f",
            self.format_type,
            "-r",
            str(self.sample_rate),
            "-c",
            str(self.channels),
        ]

        def stream_thread():
            try:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                self._is_recording = True

                while not self._stop_recording.is_set():
                    # Read from stdout pipe
                    audio_data = process.stdout.read(buffer_size)
                    if not audio_data:
                        break
                    # Call the callback with the audio data
                    callback(audio_data)

                # Clean up
                if process.poll() is None:
                    process.terminate()
                    process.wait()

                self._is_recording = False

            except Exception as e:
                self._is_recording = False
                print(f"Stream recording error: {str(e)}")

        # Start thread
        self._record_thread = threading.Thread(target=stream_thread)
        self._record_thread.daemon = True
        self._record_thread.start()

        return self._record_thread

    def play(self, filepath: str) -> None:
        """
        Play audio from a file.

        Args:
            filepath: Path to the audio file to play

        Raises:
            AudioError: If playback fails or another playback is in progress
        """
        if self._is_playing:
            raise AudioError("Playback already in progress")

        if not os.path.exists(filepath):
            raise AudioError(f"Audio file not found: {filepath}")

        # Build command
        cmd = ["aplay", "-D", self.output_device, filepath]

        try:
            with self._lock:
                self._is_playing = True
                self._stop_playback.clear()

                def play_thread():
                    proc = subprocess.Popen(cmd)
                    # Wait for stop event or completion
                    while not self._stop_playback.is_set():
                        if proc.poll() is not None:
                            break
                        time.sleep(0.1)
                    # Kill if still running
                    if proc.poll() is None:
                        proc.terminate()
                        proc.wait()

                    with self._lock:
                        self._is_playing = False

                self._play_thread = threading.Thread(target=play_thread)
                self._play_thread.start()

        except Exception as e:
            self._is_playing = False
            raise AudioError(f"Playback failed: {str(e)}")

    def stop_playback(self) -> None:
        """
        Stop an ongoing playback.

        Raises:
            AudioError: If no playback is in progress
        """
        if not self._is_playing:
            raise AudioError("No playback in progress")

        with self._lock:
            self._stop_playback.set()
            if self._play_thread and self._play_thread.is_alive():
                self._play_thread.join(timeout=2)

    def stream_play(
        self,
        audio_data: bytes | BinaryIO,
        format_type: str | None = None,
        sample_rate: int | None = None,
        channels: int | None = None,
    ) -> None:
        """
        Play audio from a stream (bytes or file-like object).

        Args:
            audio_data: Audio data as bytes or file-like object
            format_type: Audio format override (default: use instance format)
            sample_rate: Sample rate override (default: use instance rate)
            channels: Channels override (default: use instance channels)

        Raises:
            AudioError: If playback fails or another playback is in progress
        """
        if self._is_playing:
            raise AudioError("Playback already in progress")

        # Use provided params or defaults
        fmt = format_type or self.format_type
        rate = sample_rate or self.sample_rate
        chans = channels or self.channels

        # Build command
        cmd = ["aplay", "-D", self.output_device, "-f", fmt, "-r", str(rate), "-c", str(chans)]

        try:
            with self._lock:
                self._is_playing = True
                self._stop_playback.clear()

                def play_thread():
                    # Create a subprocess
                    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

                    try:
                        # Handle different input types
                        if isinstance(audio_data, bytes):
                            proc.stdin.write(audio_data)
                            proc.stdin.close()
                        else:
                            # Assume file-like object
                            while chunk := audio_data.read(4096):
                                if self._stop_playback.is_set():
                                    break
                                proc.stdin.write(chunk)
                            proc.stdin.close()

                        # Wait for process to complete
                        while not self._stop_playback.is_set():
                            if proc.poll() is not None:
                                break
                            time.sleep(0.1)

                    except Exception as e:
                        print(f"Stream playback error: {str(e)}")
                    finally:
                        # Ensure process is terminated
                        if proc.poll() is None:
                            proc.terminate()
                            proc.wait()

                        with self._lock:
                            self._is_playing = False

                self._play_thread = threading.Thread(target=play_thread)
                self._play_thread.start()

        except Exception as e:
            self._is_playing = False
            raise AudioError(f"Stream playback failed: {str(e)}")

    def is_recording(self) -> bool:
        """
        Check if recording is in progress.

        Returns:
            bool: True if recording is in progress
        """
        return self._is_recording

    def is_playing(self) -> bool:
        """
        Check if playback is in progress.

        Returns:
            bool: True if playback is in progress
        """
        return self._is_playing

    def close(self) -> None:
        """
        Clean up resources.
        """
        if self._is_recording:
            self.stop_recording()

        if self._is_playing:
            self.stop_playback()
