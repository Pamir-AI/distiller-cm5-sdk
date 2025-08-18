# Distiller CM5 SDK

[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](https://github.com/Pamir-AI/distiller-cm5-sdk)
[![Platform](https://img.shields.io/badge/platform-ARM64%20Linux-green.svg)](https://github.com/Pamir-AI/distiller-cm5-sdk)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Build](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com/Pamir-AI/distiller-cm5-sdk)

Python SDK for hardware control and AI capabilities on ARM64 Linux devices (Raspberry Pi CM5/Distiller devices). Provides comprehensive hardware drivers for audio, camera, e-ink display, and LED control, plus AI capabilities including ASR (Parakeet/Whisper) and TTS (Piper).

## Table of Contents

- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Verification](#verification)
- [Hardware Modules](#hardware-modules)
  - [Audio Control](#audio-control)
  - [Camera Control](#camera-control)
  - [E-ink Display](#e-ink-display)
  - [LED Control](#led-control)
- [AI Modules](#ai-modules)
  - [Speech Recognition (Parakeet)](#speech-recognition-parakeet)
  - [Text-to-Speech (Piper)](#text-to-speech-piper)
  - [Whisper ASR (Optional)](#whisper-asr-optional)
- [Configuration & Development](#configuration--development)
  - [Display Configuration](#display-configuration)
  - [Audio Configuration](#audio-configuration)
  - [Development Commands](#development-commands)
  - [Architecture Overview](#architecture-overview)
- [Integration Example](#integration-example)
- [Reference & Support](#reference--support)
  - [System Requirements](#system-requirements)
  - [Troubleshooting](#troubleshooting)
  - [Contributing](#contributing)
  - [License](#license)

## Quick Start

### Prerequisites

- **Operating System**: ARM64 Linux (Ubuntu 22.04+ recommended)
- **Hardware Platform**: Raspberry Pi CM5 or compatible ARM64 device
- **Python**: 3.11+ (automatically installed with package)
- **Permissions**: sudo access for installation and hardware control

### Installation

**Step 1: Clone and Build**
```bash
git clone https://github.com/Pamir-AI/distiller-cm5-sdk.git
cd distiller-cm5-sdk

# Make build scripts executable
chmod +x build.sh build-deb.sh

# Download AI models and build package
./build.sh                    # Standard models only
./build-deb.sh               # Build Debian package
```

**Step 2: Install Package**
```bash
sudo dpkg -i dist/distiller-cm5-sdk_*_arm64.deb
sudo apt-get install -f       # Install any missing dependencies
```

**Step 3: Activate Environment**
```bash
source /opt/distiller-cm5-sdk/activate.sh
```

### Verification

```bash
# Test SDK import
python -c "import distiller_cm5_sdk; print('SDK imported successfully!')"

# Check hardware modules
python -c "
from distiller_cm5_sdk.hardware.audio import Audio
from distiller_cm5_sdk.hardware.camera import Camera
from distiller_cm5_sdk.hardware.eink import Display
from distiller_cm5_sdk.hardware.sam import LED
print('All hardware modules imported successfully!')
"

# Test AI modules
python -c "
from distiller_cm5_sdk.parakeet import Parakeet
from distiller_cm5_sdk.piper import Piper
print('AI modules imported successfully!')
"
```

## Hardware Modules

### Audio Control

Control microphone gain, speaker volume, and handle audio recording/playback using ALSA.

**Key Features:**
- Static and instance-based configuration
- Real-time recording and playback
- Configurable gain and volume levels (0-100%)
- Support for various audio formats

**Basic Usage:**
```python
from distiller_cm5_sdk.hardware.audio import Audio

# Configure audio levels (static methods - persist across instances)
Audio.set_mic_gain_static(85)        # Set microphone gain to 85%
Audio.set_speaker_volume_static(70)  # Set speaker volume to 70%

# Check current levels
print(f"Mic gain: {Audio.get_mic_gain_static()}%")
print(f"Speaker volume: {Audio.get_speaker_volume_static()}%")

# Create audio instance for recording/playback
audio = Audio(auto_check_config=True)

# Record audio for 5 seconds
audio.record("recording.wav", duration=5)

# Play audio file
audio.play("recording.wav")

# Wait for playback to complete, then stop
import time
time.sleep(3)
audio.stop_playback()

# Clean up resources
audio.close()
```

### Camera Control

Capture images and record video using V4L2-compatible cameras with OpenCV integration.

**Key Features:**
- Configurable resolution, framerate, and format
- Direct image capture with optional auto-save
- Video streaming capabilities
- Support for multiple camera formats (BGR, RGB, grayscale)

**Basic Usage:**
```python
from distiller_cm5_sdk.hardware.camera import Camera
import time

# Initialize camera with custom settings
camera = Camera(
    resolution=(640, 480),
    framerate=30,
    format="bgr",
    auto_check_config=True
)

# Capture image and save directly
image_array = camera.capture_image("photo.jpg")
print(f"Captured image shape: {image_array.shape}")

# Start video streaming
def process_frame(frame):
    print(f"Received frame: {frame.shape}")

camera.start_stream(callback=process_frame)
time.sleep(5)  # Stream for 5 seconds
camera.stop_stream()

# Clean up
camera.cleanup()
```

### E-ink Display

High-performance e-ink display control with multi-format support, intelligent caching, and configurable firmware.

**Key Features:**
- **Universal Format Support**: JPEG, PNG, BMP, TIFF, WebP, GIF, ICO, PNM, TGA, DDS
- **Intelligent Caching**: LRU cache with persistence reduces repeated conversions by 90%+
- **Rust Processing**: Native performance - 2-3x faster than PIL-based processing
- **Multiple Display Types**: EPD122x250 (122×250px), EPD240x416 (240×416px)
- **Smart Scaling**: Letterbox, crop, stretch with aspect ratio preservation

**Configuration Priority:**
1. Environment variable: `DISTILLER_EINK_FIRMWARE`
2. Config files: `/opt/distiller-cm5-sdk/eink.conf`
3. Default: `EPD122x250`

**Basic Usage:**
```python
from distiller_cm5_sdk.hardware.eink import (
    Display, display_image_auto, set_default_firmware, 
    FirmwareType, ScalingMethod, DitheringMethod
)

# Configure display firmware
set_default_firmware(FirmwareType.EPD240x416)

# Quick display (any format, automatically cached)
display_image_auto("photo.jpg")
display_image_auto("document.webp")
display_image_auto("banner.png")

# Advanced usage with custom options
display_image_auto(
    "wide_image.png",
    scaling=ScalingMethod.CROP_CENTER,
    dithering=DitheringMethod.FLOYD_STEINBERG
)

# Using Display class for more control
with Display(cache_size=200, enable_cache=True) as display:
    # Display images with caching
    display.display_image_auto("logo.png")
    display.display_image_auto("menu.jpg")
    
    # Check cache performance
    stats = Display.get_cache_stats()
    print(f"Cache: {stats['entries']} images, {stats['total_bytes']} bytes")
    
    # Clear display
    display.clear()
```

**Environment Configuration:**
```bash
# Set firmware type via environment variable
export DISTILLER_EINK_FIRMWARE="EPD240x416"
```

**Config File (`/opt/distiller-cm5-sdk/eink.conf`):**
```ini
# E-ink Display Configuration
firmware=EPD240x416
```

### LED Control

RGB LED control via sysfs interface with support for multiple LEDs and color patterns.

**Key Features:**
- Individual LED control or all-LED operations
- RGB color control (0-255 per component)
- Brightness control (0-255)
- Multiple LED discovery and management

**Basic Usage:**
```python
from distiller_cm5_sdk.hardware.sam import LED

# Initialize LED controller (may require sudo)
led = LED(use_sudo=True)

# Discover available LEDs
available_leds = led.get_available_leds()
print(f"Available LEDs: {available_leds}")

if available_leds:
    led_id = available_leds[0]  # Use first available LED
    
    # Set individual LED color and brightness
    led.set_rgb_color(led_id, 255, 0, 0)  # Red
    led.set_brightness(led_id, 75)        # 75% brightness
    
    import time
    time.sleep(2)
    
    # Control all LEDs at once
    led.set_color_all(0, 255, 0)      # Green
    led.set_brightness_all(50)        # 50% brightness
    time.sleep(2)
    
    # Turn off all LEDs
    led.turn_off_all()
```

**Color Cycling Example:**
```python
import colorsys
import time

led = LED(use_sudo=True)
leds = led.get_available_leds()

if leds:
    led_id = leds[0]
    
    # Cycle through rainbow colors
    for hue in range(0, 360, 10):
        r, g, b = colorsys.hsv_to_rgb(hue/360.0, 1.0, 1.0)
        led.set_rgb_color(led_id, int(r*255), int(g*255), int(b*255))
        time.sleep(0.1)
    
    led.turn_off(led_id)
```

## AI Modules

### Speech Recognition (Parakeet)

Real-time speech recognition with Voice Activity Detection (VAD) using Parakeet ASR models.

**Key Features:**
- Voice Activity Detection (VAD) with configurable silence duration
- Real-time transcription with automatic recording
- Push-to-talk mode support
- Generator-based API for continuous processing

**Auto-Recording with VAD:**
```python
from distiller_cm5_sdk.parakeet import Parakeet

# Initialize with VAD (1 second silence duration)
parakeet = Parakeet(vad_silence_duration=1.0)

print("Say something (say 'stop' to exit):")
try:
    for text in parakeet.auto_record_and_transcribe():
        if text.strip():
            print(f"You said: {text}")
            if text.lower() == "stop":
                break
except Exception as e:
    print(f"Error: {e}")
finally:
    parakeet.cleanup()
```

**Push-to-Talk Mode:**
```python
from distiller_cm5_sdk.parakeet import Parakeet
import time

parakeet = Parakeet()

try:
    # Start recording
    print("Recording for 5 seconds...")
    parakeet.start_recording()
    time.sleep(5)
    
    # Stop recording and get audio data
    audio_data = parakeet.stop_recording()
    
    # Transcribe the recorded audio
    print("Transcribing...")
    for text in parakeet.transcribe_buffer(audio_data):
        print(f"Transcribed: {text}")
        
finally:
    parakeet.cleanup()
```

### Text-to-Speech (Piper)

High-quality speech synthesis using Piper TTS with configurable audio output.

**Key Features:**
- Direct audio streaming to speakers
- Audio file generation
- Volume control (0-100%)
- Custom sound card support

**Direct Speech Output:**
```python
from distiller_cm5_sdk.piper import Piper

# Initialize Piper TTS
piper = Piper()

# Speak directly to default audio device
piper.speak_stream("Hello from Distiller CM5!", volume=70)

# Use specific sound card
piper.speak_stream(
    "Testing custom audio device",
    volume=60,
    sound_card_name="snd_rpi_pamir_ai_soundcard"
)

# Variable volume demonstration
for volume in [30, 50, 70, 90]:
    piper.speak_stream(f"Volume level {volume}", volume=volume)
    import time
    time.sleep(1)
```

**Audio File Generation:**
```python
from distiller_cm5_sdk.piper import Piper
import os

piper = Piper()

# Generate audio file
text = "This text will be saved as an audio file"
wav_path = piper.get_wav_file_path(text)

print(f"Audio saved to: {wav_path}")

# Verify file creation
if os.path.exists(wav_path):
    size = os.path.getsize(wav_path)
    print(f"Generated file size: {size} bytes")
```

### Whisper ASR (Optional)

Alternative speech recognition using Whisper models (requires additional build step).

**Installation:**
```bash
# Include Whisper models in build
./build.sh --whisper
./build-deb.sh whisper
```

**Usage:**
```python
from distiller_cm5_sdk.whisper import FastWhisper

# Usage similar to Parakeet
whisper = FastWhisper()
# (API methods similar to Parakeet)
```

## Configuration & Development

### Display Configuration

Configure e-ink display firmware type using multiple methods (priority order):

**1. Environment Variable (Highest Priority):**
```bash
export DISTILLER_EINK_FIRMWARE="EPD240x416"
python your_script.py
```

**2. Config File:**
```bash
# Create config file
echo "firmware=EPD240x416" > /opt/distiller-cm5-sdk/eink.conf
```

**3. Programmatic (Runtime):**
```python
from distiller_cm5_sdk.hardware.eink import set_default_firmware, FirmwareType

# Using enum
set_default_firmware(FirmwareType.EPD240x416)

# Using string
set_default_firmware("EPD240x416")

# Check current setting
from distiller_cm5_sdk.hardware.eink import get_default_firmware
print(f"Current firmware: {get_default_firmware()}")
```

### Audio Configuration

```python
from distiller_cm5_sdk.hardware.audio import Audio

# Static configuration (persists across instances)
Audio.set_mic_gain_static(85)        # 0-100%
Audio.set_speaker_volume_static(70)  # 0-100%

# Check current levels
gain = Audio.get_mic_gain_static()
volume = Audio.get_speaker_volume_static()
print(f"Gain: {gain}%, Volume: {volume}%")

# Instance-specific configuration
audio = Audio()
audio.set_speaker_volume(60)  # Instance-specific setting
```

### Development Commands

**Package Management (use uv, not pip):**
```bash
# Add/remove dependencies
uv add <package>
uv remove <package>
uv sync                    # Update all packages
uv tree                    # Show dependency tree
```

**Building and Testing:**
```bash
# Model download
./build.sh                 # Standard models
./build.sh --whisper       # Include Whisper models

# Package building
./build-deb.sh             # Standard build
./build-deb.sh clean       # Clean previous builds
./build-deb.sh whisper     # Build with Whisper models

# Testing hardware modules
python src/distiller_cm5_sdk/hardware/audio/_audio_test.py
python src/distiller_cm5_sdk/hardware/camera/_camera_unit_test.py
python src/distiller_cm5_sdk/hardware/eink/_display_test.py

# Linting and formatting
ruff check src/
ruff format src/
```

### Architecture Overview

**Core Architecture:**
- **Target Platform**: ARM64 Linux only (aarch64)
- **Package Manager**: uv (not pip) for dependency management  
- **Installation Location**: Self-contained in `/opt/distiller-cm5-sdk/`
- **Python Version**: 3.11+ required
- **Build System**: Debian packaging with custom build scripts

**Key Components:**
- **Native Libraries**: Rust-based e-ink driver (`libdistiller_display_sdk_shared.so`)
- **Model Management**: Automatic path resolution (development vs production)
- **Hardware Abstraction**: Each hardware component has dedicated module with error handling
- **AI Integration**: Pre-configured models with automatic download

**Directory Structure:**
```
src/distiller_cm5_sdk/
├── hardware/          # Hardware control modules
│   ├── audio/         # ALSA audio capture/playback
│   ├── camera/        # V4L2 camera control  
│   ├── eink/          # Rust-based e-ink display + Python wrapper
│   └── sam/           # I2C/SPI LED control
├── parakeet/          # Parakeet ASR + VAD
├── piper/             # Piper TTS engine
└── whisper/           # Whisper ASR (optional)
```

## Integration Example

**Multi-Hardware Coordination:**
```python
from distiller_cm5_sdk.hardware.audio import Audio
from distiller_cm5_sdk.hardware.camera import Camera
from distiller_cm5_sdk.hardware.eink import Display
from distiller_cm5_sdk.hardware.sam import LED
from distiller_cm5_sdk.parakeet import Parakeet
from distiller_cm5_sdk.piper import Piper
import time

# Initialize all components
audio = Audio()
camera = Camera()
display = Display()
led = LED(use_sudo=True)
parakeet = Parakeet(vad_silence_duration=1.0)
piper = Piper()

try:
    # Configure audio levels
    Audio.set_mic_gain_static(85)
    Audio.set_speaker_volume_static(70)
    
    # Visual feedback: Blue LED during recording
    leds = led.get_available_leds()
    if leds:
        led.set_rgb_color(leds[0], 0, 0, 255)  # Blue
    
    # Capture image and record audio simultaneously
    print("Capturing image and recording audio...")
    image = camera.capture_image("capture.jpg")
    audio_data = audio.record("audio.wav", duration=3)
    
    # Process captured content
    display.display_image_auto("capture.jpg")
    
    # Transcribe recorded audio
    for text in parakeet.transcribe_buffer(audio_data):
        if text.strip():
            print(f"Transcribed: {text}")
            # Speak the transcription
            piper.speak_stream(f"You said: {text}", volume=60)
    
    # Success indication: Green LED
    if leds:
        led.set_rgb_color(leds[0], 0, 255, 0)  # Green
    time.sleep(2)
    
finally:
    # Clean up resources
    if leds:
        led.turn_off_all()
    display.clear()
    camera.cleanup()
    audio.close()
    parakeet.cleanup()
    print("Cleanup completed")
```

## Reference & Support

### System Requirements

**Operating System:**
- ARM64 Linux (Ubuntu 22.04+ recommended)
- Raspberry Pi OS (64-bit)
- Other ARM64 Linux distributions

**Hardware Requirements:**
- **Memory**: 4GB+ RAM (8GB+ recommended for optimal performance)
- **Storage**: 2GB+ free space (4GB+ with Whisper models)
- **Audio**: ALSA-compatible audio system
- **Camera**: V4L2-compatible cameras (USB, CSI)
- **Display**: SPI-connected e-ink displays
- **LEDs**: I2C/SPI-connected LED controllers

**Software Dependencies:**
- Python 3.11+ (automatically installed)
- Build tools: gcc, make, pkg-config, build-essential
- Audio libraries: ALSA, PortAudio
- Rust toolchain (for e-ink display library compilation)

### Troubleshooting

**Common Issues:**

1. **Import Errors:**
   ```bash
   # Activate SDK environment
   source /opt/distiller-cm5-sdk/activate.sh
   
   # Check Python path
   echo $PYTHONPATH
   python -c "import sys; print(sys.path)"
   ```

2. **Audio Device Issues:**
   ```bash
   # List audio devices
   aplay -l && arecord -l
   
   # Add user to audio group
   sudo usermod -a -G audio $USER
   
   # Test audio output
   speaker-test -t wav -c 2
   ```

3. **Camera Access Problems:**
   ```bash
   # Check camera devices
   ls -la /dev/video*
   
   # Add user to video group
   sudo usermod -a -G video $USER
   
   # Test with v4l2
   v4l2-ctl --list-devices
   ```

4. **E-ink Display Issues:**
   ```bash
   # Check SPI devices
   ls -la /dev/spi*
   
   # Verify firmware configuration
   python -c "from distiller_cm5_sdk.hardware.eink import get_default_firmware; print(get_default_firmware())"
   
   # Clear cache if needed
   python -c "from distiller_cm5_sdk.hardware.eink import Display; Display.clear_cache()"
   ```

5. **Permission Issues:**
   ```bash
   # LED control requires sudo or proper permissions
   sudo python your_led_script.py
   
   # Or use LED with sudo mode
   led = LED(use_sudo=True)
   ```

### Contributing

**Development Setup:**
1. Fork the repository
2. Clone: `git clone https://github.com/your-username/distiller-cm5-sdk.git`
3. Create branch: `git checkout -b feature/your-feature`
4. Make changes following existing patterns
5. Test thoroughly: `./build.sh && ./build-deb.sh`
6. Submit pull request with detailed description

**Code Standards:**
- Follow PEP 8 for Python formatting
- Use type hints for all function signatures
- Include comprehensive error handling
- Add docstrings for public functions
- Update tests for new functionality

For detailed development guidelines, see [CLAUDE.md](CLAUDE.md).

### License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.

**Links:**
- [GitHub Repository](https://github.com/Pamir-AI/distiller-cm5-sdk)
- [Documentation](https://github.com/Pamir-AI/distiller-cm5-sdk/blob/main/CLAUDE.md)
- [Issues & Support](https://github.com/Pamir-AI/distiller-cm5-sdk/issues)

---

**Distiller CM5 SDK v0.2.0** - Hardware Control and AI for ARM64 Linux