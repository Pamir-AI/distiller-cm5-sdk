# Distiller CM5 SDK

Python SDK for the Distiller CM5 platform, providing hardware control, audio processing, computer vision, and AI capabilities. The SDK is designed as a self-contained environment using **uv** for package management.

## Quick Start

### Prerequisites

- **Python** (automatically installed with the package)
- **ARM64 Linux system** (CM5 platform)
- **uv package manager** (automatically installed during setup)

### Installation

1. **Build the Debian Package:**
   ```bash
   git clone https://github.com/Pamir-AI/distiller-cm5-sdk.git
   cd distiller-cm5-sdk
   
   # Make build scripts executable
   chmod +x build.sh build-deb.sh
   
   # Download models and build package
   ./build.sh                    # Download models (excluding Whisper)
   ./build-deb.sh               # Build Debian package
   ```

2. **Install the Package:**
   ```bash
   sudo dpkg -i dist/distiller-cm5-sdk_*_arm64.deb
   sudo apt-get install -f       # Install any missing dependencies
   ```

3. **Verify Installation:**
   ```bash
   source /opt/distiller-cm5-sdk/activate.sh
   python -c "import distiller_cm5_sdk; print('SDK imported successfully!')"
   ```

## Package Structure

The SDK installs to `/opt/distiller-cm5-sdk/` with the following structure:

```
/opt/distiller-cm5-sdk/
├── distiller_cm5_sdk/           # Python SDK modules
│   ├── __init__.py
│   ├── hardware/                # Hardware control modules
│   │   ├── audio/               # Audio capture/playback
│   │   ├── camera/              # Camera control
│   │   ├── eink/                # E-ink display control
│   │   └── sam/                 # LED control
│   ├── parakeet/                # Parakeet ASR + VAD
│   ├── piper/                   # Piper TTS
│   └── whisper/                 # Whisper ASR (optional)
├── models/                      # AI model files
│   ├── parakeet/               # Parakeet ASR models
│   │   ├── encoder.onnx
│   │   ├── decoder.onnx
│   │   ├── joiner.onnx
│   │   ├── tokens.txt
│   │   └── silero_vad.onnx
│   ├── piper/                  # Piper TTS models and executable
│   │   ├── en_US-amy-medium.onnx
│   │   ├── en_US-amy-medium.onnx.json
│   │   └── piper/              # Piper executable directory
│   │       ├── piper           # Main executable
│   │       ├── libespeak-ng.so.1
│   │       └── ...             # Other required libraries
│   └── whisper/               # Whisper models (optional)
├── lib/                        # Native libraries
│   └── libdistiller_display_sdk_shared.so
├── venv/                       # Python 3.11 virtual environment (uv-managed)
├── activate.sh                 # Environment activation script
├── pyproject.toml              # uv configuration
├── requirements.txt            # Legacy compatibility
└── README                      # Installation notes
```

## Integration with Other Projects

### Using the SDK in Dependent Projects

For projects like `distiller-cm5-mcp-hub` and `distiller-cm5-services`, integrate the SDK by setting up the environment properly:

#### Method 1: Environment Variables (Recommended)

```bash
# Set up environment variables in your project
export PYTHONPATH="/opt/distiller-cm5-sdk:$PYTHONPATH"
export LD_LIBRARY_PATH="/opt/distiller-cm5-sdk/lib:$LD_LIBRARY_PATH"

# Activate the SDK's virtual environment
source /opt/distiller-cm5-sdk/venv/bin/activate

# Run your project
python your_project.py
```

#### Method 2: Project Setup Script

Create a setup script for your dependent project:

```bash
#!/bin/bash
# setup_sdk.sh for your project

# Check if SDK is installed
if [ ! -d "/opt/distiller-cm5-sdk" ]; then
    echo "Error: Distiller CM5 SDK not found. Please install it first."
    exit 1
fi

# Activate SDK environment
source /opt/distiller-cm5-sdk/activate.sh

# Your project-specific setup here
echo "SDK environment activated for $(basename $PWD)"
```

#### Method 3: Python Code Integration

In your Python code, add the SDK path programmatically:

```python
import sys
import os

# Add SDK to Python path
sdk_path = "/opt/distiller-cm5-sdk"
if sdk_path not in sys.path:
    sys.path.insert(0, sdk_path)

# Set library path for native libraries
os.environ["LD_LIBRARY_PATH"] = f"/opt/distiller-cm5-sdk/lib:{os.environ.get('LD_LIBRARY_PATH', '')}"

# Now you can import SDK modules
from distiller_cm5_sdk.hardware.audio import Audio
from distiller_cm5_sdk.parakeet import Parakeet
from distiller_cm5_sdk.piper import Piper
```

### Docker Integration

For containerized dependent projects:

```dockerfile
# Dockerfile example
FROM ubuntu:22.04

# Install the SDK package
COPY dist/distiller-cm5-sdk_*_arm64.deb /tmp/
RUN dpkg -i /tmp/distiller-cm5-sdk_*_arm64.deb && apt-get install -f

# Set environment variables
ENV PYTHONPATH="/opt/distiller-cm5-sdk:$PYTHONPATH"
ENV LD_LIBRARY_PATH="/opt/distiller-cm5-sdk/lib:$LD_LIBRARY_PATH"

# Your project setup
COPY . /app
WORKDIR /app

# Use the SDK's virtual environment
RUN /opt/distiller-cm5-sdk/venv/bin/pip install -r requirements.txt

CMD ["/opt/distiller-cm5-sdk/venv/bin/python", "main.py"]
```

## Development and Package Management

### Using uv for Package Management

The SDK uses **uv** for fast, reliable Python package management:

```bash
# Navigate to SDK directory
cd /opt/distiller-cm5-sdk

# Add new packages
uv add numpy matplotlib

# Remove packages
uv remove numpy

# Update all packages
uv sync

# Install from requirements
uv sync --frozen

# Show dependency tree
uv tree
```

### Development Environment

For development work:

```bash
# Activate the SDK environment
source /opt/distiller-cm5-sdk/activate.sh

# Your development environment is now ready
python -c "import distiller_cm5_sdk; print('Development environment ready!')"
```

## SDK Module Usage

### Audio Processing with Parakeet (ASR + VAD)

```python
from distiller_cm5_sdk.parakeet import Parakeet
import logging

# Configure logging for debugging
logging.basicConfig(level=logging.INFO)

# Initialize with voice activity detection
parakeet = Parakeet(vad_silence_duration=1.0)

# Auto-record and transcribe with VAD
print("Starting voice recognition. Say 'stop' to exit.")
try:
    for text in parakeet.auto_record_and_transcribe():
        if text.strip():
            print(f"Transcribed: {text}")
            if text.lower() == "stop":
                break
except Exception as e:
    print(f"Error during transcription: {e}")
finally:
    parakeet.cleanup()

# Push-to-talk transcription example
def ptt_transcription_example():
    """Example of push-to-talk transcription workflow"""
    parakeet = Parakeet()
    
    try:
        print("Starting recording for 5 seconds...")
        parakeet.start_recording()
        
        # Simulate user speaking for 5 seconds
        import time
        time.sleep(5)
        
        print("Stopping recording and transcribing...")
        audio_data = parakeet.stop_recording()
        
        for text in parakeet.transcribe_buffer(audio_data):
            print(f"PTT Transcribed: {text}")
            
    except Exception as e:
        print(f"Error during PTT transcription: {e}")
    finally:
        parakeet.cleanup()

# Run the example
if __name__ == "__main__":
    ptt_transcription_example()
```

### Text-to-Speech with Piper

```python
from distiller_cm5_sdk.piper import Piper
import os

# Initialize Piper TTS
piper = Piper()

# Generate speech to file
def text_to_file_example():
    """Convert text to speech and save to file"""
    text = "Hello, this is a comprehensive test of the Piper text-to-speech system."
    try:
        wav_path = piper.get_wav_file_path(text)
        print(f"Audio saved to: {wav_path}")
        
        # Verify file exists and has content
        if os.path.exists(wav_path):
            size = os.path.getsize(wav_path)
            print(f"Generated audio file size: {size} bytes")
        else:
            print("Warning: Audio file was not created")
            
    except Exception as e:
        print(f"Error generating audio file: {e}")

# Stream speech directly to speakers
def text_to_speech_example():
    """Stream text-to-speech directly to audio output"""
    messages = [
        "Welcome to the Distiller CM5 SDK",
        "This is a demonstration of the text-to-speech capabilities",
        "The system supports various volume levels and audio devices"
    ]
    
    for i, message in enumerate(messages):
        try:
            print(f"Speaking message {i+1}: {message}")
            piper.speak_stream(message, volume=50)
            
            # Wait a moment between messages
            import time
            time.sleep(1)
            
        except Exception as e:
            print(f"Error speaking message {i+1}: {e}")

# Use specific sound card
def advanced_audio_output():
    """Demonstrate advanced audio output configuration"""
    try:
        # Test with specific sound card
        piper.speak_stream(
            "Testing audio output with specific sound card configuration", 
            volume=70, 
            sound_card_name="snd_rpi_pamir_ai_soundcard"
        )
        
        # Test volume variations
        for volume in [30, 50, 70, 90]:
            piper.speak_stream(f"Volume level {volume}", volume=volume)
            
    except Exception as e:
        print(f"Error with advanced audio output: {e}")

# Run examples
if __name__ == "__main__":
    text_to_file_example()
    text_to_speech_example()
    advanced_audio_output()
```

### Audio Hardware Control

```python
from distiller_cm5_sdk.hardware.audio import Audio
import time

# Initialize audio system
audio = Audio()

def audio_configuration_example():
    """Demonstrate audio system configuration"""
    try:
        # Set microphone gain (0-100)
        Audio.set_mic_gain_static(85)
        print("Microphone gain set to 85%")
        
        # Set speaker volume (0-100)
        Audio.set_speaker_volume_static(70)
        print("Speaker volume set to 70%")
        
        # Verify settings
        print("Audio configuration completed successfully")
        
    except Exception as e:
        print(f"Error configuring audio: {e}")

def audio_recording_example():
    """Demonstrate audio recording and playback"""
    try:
        print("Starting 5-second audio recording...")
        audio_data = audio.record_audio(duration=5)
        
        # Save the recording
        filename = "test_recording.wav"
        audio.save_audio_to_file(audio_data, filename)
        print(f"Audio saved to: {filename}")
        
        # Wait a moment, then play back
        time.sleep(1)
        print("Playing back recorded audio...")
        audio.play_audio_file(filename)
        
    except Exception as e:
        print(f"Error during audio recording/playback: {e}")

def audio_system_info():
    """Display audio system information"""
    try:
        # This would typically include methods to get audio device info
        # Implementation depends on the actual Audio class capabilities
        print("Audio system initialized successfully")
        
    except Exception as e:
        print(f"Error getting audio system info: {e}")

# Run examples
if __name__ == "__main__":
    audio_configuration_example()
    audio_recording_example()
    audio_system_info()
```

### E-ink Display Control

The e-ink display system features high-performance image processing with multi-format support, intelligent caching, and configurable firmware for different display sizes. The system automatically converts and optimizes images from 10+ formats.

#### 🎉 New Features (v0.2.0)
- **Universal Format Support**: Display JPEG, BMP, TIFF, WebP, GIF, PNG, ICO, PNM, TGA, DDS
- **Image Caching**: LRU cache with persistence reduces repeated conversions by 90%+
- **Rust Processing**: Native performance - 2-3x faster than PIL
- **Backward Compatible**: All existing code continues to work

#### Supported Display Types
- **EPD128x250**: 128x250 pixel display (4,000 bytes, default for backward compatibility)
- **EPD240x416**: 240x416 pixel display (12,480 bytes)

#### Configuration Priority Order
The configuration system searches for settings in this priority order:
1. **Environment Variable**: `DISTILLER_EINK_FIRMWARE`
2. **Config Files**: `/opt/distiller-cm5-sdk/eink.conf`, `./eink.conf`, `~/.distiller/eink.conf`
3. **Default**: `EPD128x250` (backward compatibility)

#### Configuration Methods

**Environment Variable:**
```bash
export DISTILLER_EINK_FIRMWARE="EPD240x416"
python your_script.py
```

**Config File Example (`/opt/distiller-cm5-sdk/eink.conf`):**
```ini
# E-ink Display Configuration
# Supported firmware types:
# - EPD128x250: 128x250 pixel display (default)
# - EPD240x416: 240x416 pixel display

firmware=EPD240x416
```

**Programmatic Configuration:**
```python
from distiller_cm5_sdk.hardware.eink import (
    set_default_firmware, 
    get_default_firmware,
    initialize_display_config, 
    FirmwareType
)

# Set firmware type using enum
set_default_firmware(FirmwareType.EPD240x416)

# Set firmware type using string
set_default_firmware("EPD240x416")

# Initialize from environment/config files
initialize_display_config()

# Get current firmware configuration
current_firmware = get_default_firmware()
print(f"Current firmware: {current_firmware}")
```

#### Dynamic Dimension Updates
Display dimensions are automatically updated based on the configured firmware:
- **EPD128x250**: 128×250 pixels, 4,000 bytes array size
- **EPD240x416**: 240×416 pixels, 12,480 bytes array size

The `EinkDriver` class properties (`WIDTH`, `HEIGHT`, `ARRAY_SIZE`) are dynamically updated after initialization.

#### Usage Examples

```python
from distiller_cm5_sdk.hardware.eink import (
    Display, display_image_auto, set_default_firmware, FirmwareType
)
import os

def eink_configuration_example():
    """Demonstrate e-ink display configuration"""
    try:
        # Configure display firmware before initialization
        set_default_firmware(FirmwareType.EPD240x416)
        print("Firmware set to EPD240x416")
        
        # Alternative: Initialize from environment/config files
        # initialize_display_config()
        
    except Exception as e:
        print(f"Error configuring display: {e}")

def eink_multi_format_example():
    """Display various image formats with caching"""
    # Quick display of any format
    display_image_auto("photo.jpg")       # JPEG
    display_image_auto("document.tiff")   # TIFF
    display_image_auto("graphic.bmp")     # BMP
    display_image_auto("modern.webp")     # WebP
    
    # With Display class for more control
    with Display() as display:
        # Check supported formats
        formats = display.get_supported_formats()
        print(f"Supported: {', '.join(formats)}")
        
        # Display with caching (second call is instant)
        display.display_image_auto("logo.png")
        display.display_image_auto("logo.png")  # Uses cache!
        
        # Check cache stats
        stats = Display.get_cache_stats()
        print(f"Cached: {stats['entries']} images")

def eink_display_example():
    """E-ink display control with auto-conversion"""
    display = None
    
    try:
        # Initialize display with caching
        display = Display(cache_size=200)
        print("E-ink display initialized with caching")
        
        # Display any image format - auto-converted
        image_path = "sample_image.jpg"
        if os.path.exists(image_path):
            print(f"Displaying: {image_path}")
            display.display_image_auto(image_path)
            
            # Wait for display to update
            import time
            time.sleep(2)
            
        else:
            print(f"Sample image not found: {image_path}")
            print("Creating a test pattern instead...")
            
            # Create a simple test pattern
            # This would depend on the actual image data format expected
            print("Displaying test pattern...")
            
        # Clear display after demonstration
        print("Clearing display...")
        display.clear_display()
        
    except Exception as e:
        print(f"Error with e-ink display: {e}")
        
    finally:
        if display:
            try:
                display.cleanup()
                print("E-ink display cleanup completed")
            except Exception as e:
                print(f"Error during cleanup: {e}")

def eink_multi_firmware_example():
    """Demonstrate different firmware configurations"""
    firmware_types = [FirmwareType.EPD128x250, FirmwareType.EPD240x416]
    
    for firmware in firmware_types:
        try:
            print(f"Testing with firmware: {firmware.name}")
            
            # Set firmware type
            set_default_firmware(firmware)
            
            # Initialize display
            display = EinkDriver()
            display.initialize()
            
            # Display dimensions are now dynamic based on firmware
            print(f"Display dimensions: {display.WIDTH}x{display.HEIGHT}")
            
            # Clear display
            display.clear_display()
            display.cleanup()
            
            import time
            time.sleep(1)
            
        except Exception as e:
            print(f"Error with firmware {firmware.name}: {e}")

def eink_image_processing_example():
    """Demonstrate image processing for e-ink display"""
    try:
        # Example of different image processing options
        image_path = "input_image.jpg"
        
        if os.path.exists(image_path):
            # Process with different thresholds
            for threshold in [100, 128, 150]:
                print(f"Processing image with threshold {threshold}")
                processed_image = load_and_convert_image(
                    image_path, 
                    threshold=threshold, 
                    dither=False
                )
                
                # Display processed image
                display = EinkDriver()
                display.initialize()
                display.display_image(processed_image)
                
                # Wait between displays
                import time
                time.sleep(3)
                
                display.cleanup()
                
        else:
            print(f"Input image not found: {image_path}")
            
    except Exception as e:
        print(f"Error processing images: {e}")

# Run examples
if __name__ == "__main__":
    eink_configuration_example()
    eink_display_example()
    eink_multi_firmware_example()
    eink_image_processing_example()
```

### Camera Control

```python
from distiller_cm5_sdk.hardware.camera import Camera
import time
import os

def camera_capture_example():
    """camera capture example"""
    camera = None
    
    try:
        # Initialize camera
        camera = Camera()
        print("Camera initialized successfully")
        
        # Capture single image
        print("Capturing image...")
        image = camera.capture_image()
        
        # Save with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"captured_image_{timestamp}.jpg"
        camera.save_image(image, filename)
        
        print(f"Image saved as: {filename}")
        
        # Verify file was created
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"Image file size: {size} bytes")
        else:
            print("Warning: Image file was not created")
            
    except Exception as e:
        print(f"Error during image capture: {e}")
        
    finally:
        if camera:
            try:
                camera.cleanup()
                print("Camera cleanup completed")
            except Exception as e:
                print(f"Error during camera cleanup: {e}")

def camera_video_example():
    """video recording functionality"""
    camera = None
    
    try:
        camera = Camera()
        print("Starting video recording...")
        
        # Start recording
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        video_filename = f"recorded_video_{timestamp}.avi"
        camera.start_video_recording(video_filename)
        
        # Record for 10 seconds
        print("Recording for 10 seconds...")
        time.sleep(10)
        
        # Stop recording
        camera.stop_video_recording()
        print(f"Video recording stopped. Saved as: {video_filename}")
        
        # Verify video file
        if os.path.exists(video_filename):
            size = os.path.getsize(video_filename)
            print(f"Video file size: {size} bytes")
        else:
            print("Warning: Video file was not created")
            
    except Exception as e:
        print(f"Error during video recording: {e}")
        
    finally:
        if camera:
            try:
                camera.cleanup()
                print("Camera cleanup completed")
            except Exception as e:
                print(f"Error during camera cleanup: {e}")

def camera_settings_example():
    """camera settings and configuration"""
    camera = None
    
    try:
        camera = Camera()
        
        # This would typically include methods to configure camera settings
        # such as resolution, format, frame rate, etc.
        print("Camera settings configured successfully")
        
        # Example of multiple captures with different settings
        for i in range(3):
            print(f"Capturing image {i+1}/3...")
            image = camera.capture_image()
            filename = f"test_image_{i+1}.jpg"
            camera.save_image(image, filename)
            time.sleep(1)
            
    except Exception as e:
        print(f"Error with camera settings: {e}")
        
    finally:
        if camera:
            camera.cleanup()

# Run examples
if __name__ == "__main__":
    camera_capture_example()
    camera_video_example()
    camera_settings_example()
```

### LED Control

```python
from distiller_cm5_sdk.hardware.sam import LED
import time

def led_basic_control():
    """Basic LED control operations"""
    led = None
    
    try:
        # Initialize LED
        led = LED()
        print("LED initialized successfully")
        
        # Basic on/off control
        print("Turning LED on...")
        led.turn_on()
        time.sleep(2)
        
        print("Turning LED off...")
        led.turn_off()
        time.sleep(1)
        
        # Brightness control
        print("Testing brightness levels...")
        led.turn_on()
        for brightness in [25, 50, 75, 100]:
            print(f"Setting brightness to {brightness}%")
            led.set_brightness(brightness)
            time.sleep(1)
            
        led.turn_off()
        
    except Exception as e:
        print(f"Error with LED control: {e}")
        
    finally:
        if led:
            try:
                led.turn_off()
                print("LED turned off during cleanup")
            except Exception as e:
                print(f"Error during LED cleanup: {e}")

def led_color_control():
    """LED color control"""
    led = None
    
    try:
        led = LED()
        led.turn_on()
        
        # RGB color examples
        colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
            (255, 255, 255) # White
        ]
        
        color_names = ["Red", "Green", "Blue", "Yellow", "Magenta", "Cyan", "White"]
        
        for i, (r, g, b) in enumerate(colors):
            print(f"Setting LED color to {color_names[i]} (R:{r}, G:{g}, B:{b})")
            led.set_color(r, g, b)
            time.sleep(1.5)
            
        led.turn_off()
        
    except Exception as e:
        print(f"Error with LED color control: {e}")
        
    finally:
        if led:
            led.turn_off()

def led_pattern_example():
    """LED patterns and sequences"""
    led = None
    
    try:
        led = LED()
        
        # Breathing pattern
        print("Starting breathing pattern...")
        led.turn_on()
        led.set_color(0, 0, 255)  # Blue
        
        for cycle in range(3):
            # Fade in
            for brightness in range(0, 101, 5):
                led.set_brightness(brightness)
                time.sleep(0.05)
            
            # Fade out
            for brightness in range(100, -1, -5):
                led.set_brightness(brightness)
                time.sleep(0.05)
                
        led.turn_off()
        
        # Color cycling
        print("Starting color cycling...")
        led.turn_on()
        led.set_brightness(50)
        
        for hue in range(0, 360, 10):
            # Convert HSV to RGB (simplified)
            import colorsys
            r, g, b = colorsys.hsv_to_rgb(hue/360.0, 1.0, 1.0)
            led.set_color(int(r*255), int(g*255), int(b*255))
            time.sleep(0.1)
            
        led.turn_off()
        
    except Exception as e:
        print(f"Error with LED patterns: {e}")
        
    finally:
        if led:
            led.turn_off()

# Run examples
if __name__ == "__main__":
    led_basic_control()
    led_color_control()
    led_pattern_example()
```

## Build Process

### Model Download

The build process automatically downloads required AI models:

```bash
# Download all models except Whisper
./build.sh

# Download all models including Whisper
./build.sh whisper

# Verify model downloads
ls -la models/parakeet/
ls -la models/piper/
ls -la models/whisper/  # If Whisper was downloaded
```

### Debian Package Build

```bash
# Clean build (removes previous build artifacts)
./build-deb.sh clean

# Standard build (excludes Whisper models)
./build-deb.sh

# Build with Whisper models (larger package size)
./build-deb.sh whisper

# Verify package creation
ls -la dist/
dpkg-deb --info dist/distiller-cm5-sdk_*_arm64.deb
```

### Manual Model Downloads

If you need to manually download models:

#### Parakeet Models (Required)
- [encoder.onnx](https://huggingface.co/tommy1900/Parakeet-onnx/resolve/main/encoder.onnx)
- [decoder.onnx](https://huggingface.co/tommy1900/Parakeet-onnx/resolve/main/decoder.onnx)
- [joiner.onnx](https://huggingface.co/tommy1900/Parakeet-onnx/resolve/main/joiner.onnx)
- [tokens.txt](https://huggingface.co/tommy1900/Parakeet-onnx/resolve/main/tokens.txt)
- [silero_vad.onnx](https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx)

#### Piper Models (Required)
- [en_US-amy-medium.onnx](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx)
- [en_US-amy-medium.onnx.json](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx.json)
- [piper_arm64.tar.gz](https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_arm64.tar.gz)

#### Whisper Models (Optional)
- [faster-distil-whisper-small.en](https://huggingface.co/Systran/faster-distil-whisper-small.en) (all files)

## Package Management

### Removing the SDK

```bash
# Remove package (keeps config files)
sudo apt remove distiller-cm5-sdk

# Complete removal (removes config files and data)
sudo apt purge distiller-cm5-sdk

# Clean up unused dependencies
sudo apt autoremove

# Verify removal
dpkg -l | grep distiller-cm5-sdk
ls -la /opt/distiller-cm5-sdk/  # Should not exist after purge
```

### Updating the Package

```bash
# Build new package version
./build-deb.sh

# Install update (will upgrade existing installation)
sudo dpkg -i dist/distiller-cm5-sdk_*_arm64.deb

# Resolve any dependency conflicts
sudo apt-get install -f

# Verify update
dpkg -s distiller-cm5-sdk | grep Version
```

### Package Information

```bash
# View package details
dpkg -l | grep distiller-cm5-sdk
dpkg -L distiller-cm5-sdk  # List all files in package
dpkg -s distiller-cm5-sdk  # Show package status and metadata

# Check package integrity
dpkg -V distiller-cm5-sdk

# View package dependencies
apt depends distiller-cm5-sdk
apt rdepends distiller-cm5-sdk
```

## Troubleshooting

### Common Issues

1. **Piper executable not found:**
   - Ensure models are downloaded: `./build.sh`
   - Check path: `/opt/distiller-cm5-sdk/models/piper/piper/piper`
   - Verify executable permissions: `ls -la /opt/distiller-cm5-sdk/models/piper/piper/piper`
   - Test execution: `/opt/distiller-cm5-sdk/models/piper/piper/piper --help`

2. **Module import errors:**
   - Activate environment: `source /opt/distiller-cm5-sdk/activate.sh`
   - Check PYTHONPATH: `echo $PYTHONPATH`
   - Verify virtual environment: `which python`
   - Test Python path: `python -c "import sys; print(sys.path)"`

3. **Audio device issues:**
   - List devices: `aplay -l` and `arecord -l`
   - Check permissions: `sudo usermod -a -G audio $USER`
   - Test audio output: `speaker-test -t wav -c 2`
   - Check ALSA configuration: `cat /proc/asound/cards`

4. **Library loading errors:**
   - Check LD_LIBRARY_PATH: `echo $LD_LIBRARY_PATH`
   - Update cache: `sudo ldconfig`
   - Verify library exists: `ls -la /opt/distiller-cm5-sdk/lib/`
   - Test library loading: `ldd /opt/distiller-cm5-sdk/lib/libdistiller_display_sdk_shared.so`

5. **E-ink display issues:**
   - Check device permissions: `ls -la /dev/spi*`
   - Verify SPI interface: `lsmod | grep spi`
   - Test configuration system: `python -c "from distiller_cm5_sdk.hardware.eink import get_default_firmware, initialize_display_config; initialize_display_config(); print(f'Firmware: {get_default_firmware()}')"`
   - Check firmware configuration: `echo $DISTILLER_EINK_FIRMWARE` or `cat /opt/distiller-cm5-sdk/eink.conf`
   - Test with minimal example: `python -c "from distiller_cm5_sdk.hardware.eink import Display; print('Import successful')"`
   - Check supported formats: `python -c "from distiller_cm5_sdk.hardware.eink import Display; d = Display(); print(d.get_supported_formats())"`
   - Clear cache if needed: `python -c "from distiller_cm5_sdk.hardware.eink import Display; Display.clear_cache(); print('Cache cleared')"`
   - For dimension mismatches, verify firmware type: `python -c "from distiller_cm5_sdk.hardware.eink import FirmwareType, set_default_firmware; set_default_firmware(FirmwareType.EPD240x416); print('Firmware updated')"`

6. **Camera access problems:**
   - Check camera devices: `ls -la /dev/video*`
   - Test with v4l2: `v4l2-ctl --list-devices`
   - Verify permissions: `sudo usermod -a -G video $USER`

### E-ink Configuration Troubleshooting

**Configuration Issues:**
```bash
# Check current firmware configuration
python -c "
from distiller_cm5_sdk.hardware.eink import get_default_firmware, initialize_display_config
try:
    initialize_display_config()
    print(f'✓ Current firmware: {get_default_firmware()}')
except Exception as e:
    print(f'✗ Configuration error: {e}')
"

# Verify configuration sources
echo "Environment variable: $DISTILLER_EINK_FIRMWARE"
echo "Config file locations:"
ls -la /opt/distiller-cm5-sdk/eink.conf 2>/dev/null || echo "  /opt/distiller-cm5-sdk/eink.conf: Not found"
ls -la ./eink.conf 2>/dev/null || echo "  ./eink.conf: Not found"
ls -la ~/.distiller/eink.conf 2>/dev/null || echo "  ~/.distiller/eink.conf: Not found"
```

**Firmware Configuration Reset:**
```bash
# Reset to default firmware
python -c "
from distiller_cm5_sdk.hardware.eink import set_default_firmware, FirmwareType
set_default_firmware(FirmwareType.EPD128x250)
print('Firmware reset to EPD128x250 (default)')
"

# Set specific firmware for your display
python -c "
from distiller_cm5_sdk.hardware.eink import set_default_firmware, FirmwareType
set_default_firmware(FirmwareType.EPD240x416)
print('Firmware set to EPD240x416')
"
```

**Display Dimension Verification:**
```bash
# Check display dimensions after configuration
python -c "
from distiller_cm5_sdk.hardware.eink import Display, set_default_firmware, FirmwareType

# Test with different firmware types
for firmware in [FirmwareType.EPD128x250, FirmwareType.EPD240x416]:
    set_default_firmware(firmware)
    with Display() as display:
        print(f'{firmware}: {display.WIDTH}x{display.HEIGHT} pixels, {display.ARRAY_SIZE} bytes')
"

# Check cache and format support
python -c "
from distiller_cm5_sdk.hardware.eink import Display

with Display() as d:
    formats = d.get_supported_formats()
    stats = Display.get_cache_stats()
    print(f'Formats: {len(formats)} supported')
    print(f'Cache: {stats[\"entries\"]} entries, {stats[\"total_bytes\"]} bytes')
"
```

### Environment Verification

```bash
# Check SDK installation
ls -la /opt/distiller-cm5-sdk/
du -sh /opt/distiller-cm5-sdk/

# Verify Python environment
source /opt/distiller-cm5-sdk/activate.sh
which python
python --version
pip list | grep -i distiller

# Test imports with detailed error reporting
python -c "
import sys
import traceback

try:
    import distiller_cm5_sdk
    print('✓ Base SDK import successful')
    
    from distiller_cm5_sdk.parakeet import Parakeet
    print('✓ Parakeet import successful')
    
    from distiller_cm5_sdk.piper import Piper
    print('✓ Piper import successful')
    
    from distiller_cm5_sdk.hardware.audio import Audio
    print('✓ Audio hardware import successful')
    
    from distiller_cm5_sdk.hardware.camera import Camera
    print('✓ Camera hardware import successful')
    
    from distiller_cm5_sdk.hardware.eink import Display, display_image_auto
    print('✓ E-ink display import successful')
    
    from distiller_cm5_sdk.hardware.sam import LED
    print('✓ LED hardware import successful')
    
    print('All imports successful!')
    
except ImportError as e:
    print(f'Import error: {e}')
    traceback.print_exc()
except Exception as e:
    print(f'Other error: {e}')
    traceback.print_exc()
"

# Check file permissions
find /opt/distiller-cm5-sdk -type f -name "*.py" -exec ls -la {} \; | head -10
find /opt/distiller-cm5-sdk -type f -name "*.so" -exec ls -la {} \;

# Test hardware access
python -c "
import os
print('Audio group membership:', 'audio' in [g.gr_name for g in os.getgroups()])
print('Video group membership:', 'video' in [g.gr_name for g in os.getgroups()])
"
```

### Diagnostic Script

```bash
#!/bin/bash
# Create a diagnostic script for comprehensive troubleshooting

echo "=== Distiller CM5 SDK Diagnostic ==="
echo "Timestamp: $(date)"
echo

echo "1. System Information:"
uname -a
lsb_release -a 2>/dev/null || echo "lsb_release not available"
echo

echo "2. SDK Installation Check:"
ls -la /opt/distiller-cm5-sdk/ || echo "SDK not found"
echo

echo "3. Python Environment:"
source /opt/distiller-cm5-sdk/activate.sh 2>/dev/null || echo "Cannot activate SDK environment"
which python
python --version
echo

echo "4. Hardware Devices:"
echo "Audio devices:"
aplay -l 2>/dev/null || echo "No audio playback devices"
arecord -l 2>/dev/null || echo "No audio capture devices"
echo
echo "Video devices:"
ls -la /dev/video* 2>/dev/null || echo "No video devices found"
echo
echo "SPI devices:"
ls -la /dev/spi* 2>/dev/null || echo "No SPI devices found"
echo

echo "5. System Resources:"
df -h /opt/distiller-cm5-sdk/ 2>/dev/null || echo "Cannot check disk usage"
free -h
echo

echo "6. Package Status:"
dpkg -s distiller-cm5-sdk 2>/dev/null || echo "Package not installed"
echo

echo "=== End Diagnostic ==="
```

## System Requirements

- **OS:** ARM64 Linux (Ubuntu 22.04+ recommended)
- **Python:** 3.11 (automatically installed)
- **Memory:** 4GB+ RAM recommended (8GB+ for optimal performance)
- **Storage:** 2GB+ free space for models (4GB+ with Whisper models)
- **Audio:** ALSA-compatible audio system
- **Hardware:** CM5 platform with supported peripherals
- **Network:** Internet connection for model downloads during build
- **Permissions:** sudo access for installation and hardware access

### Hardware Support

- **Audio Interface:** ALSA-compatible sound cards and USB audio devices
- **Camera:** V4L2-compatible cameras (USB, CSI)
- **E-ink Display:** SPI-connected e-ink displays
- **LED Controllers:** I2C/SPI-connected LED controllers
- **GPIO:** Standard GPIO pin access for hardware control

### Software Dependencies

- **Build Tools:** gcc, make, pkg-config, build-essential
- **Audio Libraries:** ALSA, PortAudio, PulseAudio (optional)
- **Python Libraries:** Managed automatically by uv
- **Native Libraries:** Rust toolchain for e-ink display library

## Integration Examples

### Service Integration

```python
#!/usr/bin/env python3
"""
voice service integration example.
Demonstrates proper SDK initialization, error handling, and cleanup.
"""

import os
import sys
import logging
import signal
import threading
from typing import Optional

# Ensure SDK is in path
sys.path.insert(0, '/opt/distiller-cm5-sdk')

from distiller_cm5_sdk.parakeet import Parakeet
from distiller_cm5_sdk.piper import Piper
from distiller_cm5_sdk.hardware.audio import Audio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VoiceService:
    """voice service implementation with error handling."""
    
    def __init__(self, vad_silence_duration: float = 1.0):
        self.asr: Optional[Parakeet] = None
        self.tts: Optional[Piper] = None
        self.audio: Optional[Audio] = None
        self.running = False
        self.shutdown_event = threading.Event()
        
        try:
            # Initialize audio system
            self.audio = Audio()
            Audio.set_mic_gain_static(85)
            Audio.set_speaker_volume_static(70)
            
            # Initialize ASR with VAD
            self.asr = Parakeet(vad_silence_duration=vad_silence_duration)
            
            # Initialize TTS
            self.tts = Piper()
            
            logger.info("Voice service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize voice service: {e}")
            self.cleanup()
            raise
    
    def process_voice_command(self) -> None:
        """Process voice commands with proper error handling."""
        if not self.asr or not self.tts:
            logger.error("Voice service not properly initialized")
            return
        
        self.running = True
        logger.info("Starting voice command processing")
        
        try:
            # Listen for voice input
            for text in self.asr.auto_record_and_transcribe():
                if self.shutdown_event.is_set():
                    break
                    
                if text.strip():
                    logger.info(f"Heard: {text}")
                    
                    # Process command and respond
                    response = self.handle_command(text)
                    if response:
                        self.tts.speak_stream(response)
                    
                    # Check for exit command
                    if text.lower() in ['exit', 'quit', 'stop']:
                        break
                        
        except KeyboardInterrupt:
            logger.info("Voice processing interrupted by user")
        except Exception as e:
            logger.error(f"Error during voice processing: {e}")
        finally:
            self.running = False
            logger.info("Voice command processing stopped")
    
    def handle_command(self, text: str) -> Optional[str]:
        """
        Process voice commands and return appropriate responses.
        
        Args:
            text: The transcribed voice command
            
        Returns:
            Response text to be spoken, or None for no response
        """
        text_lower = text.lower()
        
        # Command processing logic
        if 'hello' in text_lower:
            return "Hello! How can I help you?"
        elif 'time' in text_lower:
            import datetime
            current_time = datetime.datetime.now().strftime("%H:%M")
            return f"The current time is {current_time}"
        elif 'weather' in text_lower:
            return "I'm sorry, I don't have access to weather information right now."
        elif 'test' in text_lower:
            return "Test successful! The voice service is working properly."
        elif any(word in text_lower for word in ['exit', 'quit', 'stop']):
            return "Goodbye!"
        else:
            return f"You said: {text}"
    
    def cleanup(self) -> None:
        """Clean up resources and shut down gracefully."""
        logger.info("Cleaning up voice service resources")
        
        self.shutdown_event.set()
        
        if self.asr:
            try:
                self.asr.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up ASR: {e}")
        
        if self.tts:
            try:
                # TTS cleanup if available
                pass
            except Exception as e:
                logger.error(f"Error cleaning up TTS: {e}")
        
        if self.audio:
            try:
                # Audio cleanup if available
                pass
            except Exception as e:
                logger.error(f"Error cleaning up audio: {e}")
        
        logger.info("Voice service cleanup completed")

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    global service
    if service:
        service.cleanup()
    sys.exit(0)

# Global service instance for signal handling
service = None

def main():
    """Main entry point for the voice service."""
    global service
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize and run service
        service = VoiceService(vad_silence_duration=1.0)
        service.process_voice_command()
        
    except Exception as e:
        logger.error(f"Service failed: {e}")
        return 1
    
    finally:
        if service:
            service.cleanup()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### MCP Hub Integration

```python
#!/usr/bin/env python3
"""
MCP hub integration example.
Demonstrates multi-hardware coordination and error handling.
"""

import os
import sys
import logging
import threading
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

# Ensure SDK is in path
sys.path.insert(0, '/opt/distiller-cm5-sdk')

from distiller_cm5_sdk.hardware.audio import Audio
from distiller_cm5_sdk.hardware.camera import Camera
from distiller_cm5_sdk.hardware.eink import Display, display_image_auto
from distiller_cm5_sdk.hardware.sam import LED

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SystemStatus(Enum):
    """System status enumeration."""
    INITIALIZING = "initializing"
    READY = "ready"
    ACTIVE = "active"
    ERROR = "error"
    SHUTDOWN = "shutdown"

@dataclass
class HardwareState:
    """Hardware state tracking."""
    audio_initialized: bool = False
    camera_initialized: bool = False
    display_initialized: bool = False
    led_initialized: bool = False
    last_error: Optional[str] = None

class MCPHub:
    """
    MCP hub implementation with hardware management.
    """
    
    def __init__(self):
        self.audio: Optional[Audio] = None
        self.camera: Optional[Camera] = None
        self.display: Optional[Display] = None
        self.led: Optional[LED] = None
        
        self.status = SystemStatus.INITIALIZING
        self.hardware_state = HardwareState()
        self.shutdown_event = threading.Event()
        
        # Initialize hardware
        self._initialize_hardware()
    
    def _initialize_hardware(self) -> None:
        """Initialize all hardware components with proper error handling."""
        logger.info("Initializing MCP hub hardware")
        
        # Initialize audio
        try:
            self.audio = Audio()
            Audio.set_mic_gain_static(85)
            Audio.set_speaker_volume_static(70)
            self.hardware_state.audio_initialized = True
            logger.info("Audio system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize audio: {e}")
            self.hardware_state.last_error = str(e)
        
        # Initialize camera
        try:
            self.camera = Camera()
            self.hardware_state.camera_initialized = True
            logger.info("Camera system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            self.hardware_state.last_error = str(e)
        
        # Initialize display with caching
        try:
            self.display = Display(enable_cache=True, cache_size=100)
            self.hardware_state.display_initialized = True
            logger.info("E-ink display initialized with caching")
        except Exception as e:
            logger.error(f"Failed to initialize display: {e}")
            self.hardware_state.last_error = str(e)
        
        # Initialize LED
        try:
            self.led = LED()
            self.hardware_state.led_initialized = True
            logger.info("LED controller initialized")
        except Exception as e:
            logger.error(f"Failed to initialize LED: {e}")
            self.hardware_state.last_error = str(e)
        
        # Set system status
        if any([
            self.hardware_state.audio_initialized,
            self.hardware_state.camera_initialized,
            self.hardware_state.display_initialized,
            self.hardware_state.led_initialized
        ]):
            self.status = SystemStatus.READY
            logger.info("MCP hub initialized successfully")
        else:
            self.status = SystemStatus.ERROR
            logger.error("Failed to initialize any hardware components")
    
    def capture_and_display(self) -> Optional[Any]:
        """
        Capture image from camera and display on e-ink screen.
        
        Returns:
            Captured image data or None if operation failed
        """
        if not self.camera or not self.display:
            logger.error("Camera or display not available")
            return None
        
        try:
            logger.info("Capturing image from camera")
            image = self.camera.capture_image()
            
            # Save original image
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            image_filename = f"captured_{timestamp}.jpg"
            self.camera.save_image(image, image_filename)
            
            # Process for e-ink display
            logger.info("Processing image for e-ink display")
            display_data = load_and_convert_image(
                image_filename, 
                threshold=128, 
                dither=True
            )
            
            # Display on e-ink
            logger.info("Displaying image on e-ink screen")
            self.display.display_image(display_data)
            
            # Visual feedback with LED
            if self.led:
                self.led.turn_on()
                self.led.set_color(0, 255, 0)  # Green for success
                self.led.set_brightness(50)
                threading.Timer(2.0, lambda: self.led.turn_off()).start()
            
            logger.info("Image capture and display completed successfully")
            return image
            
        except Exception as e:
            logger.error(f"Error during capture and display: {e}")
            
            # Error indication with LED
            if self.led:
                self.led.turn_on()
                self.led.set_color(255, 0, 0)  # Red for error
                self.led.set_brightness(75)
                threading.Timer(3.0, lambda: self.led.turn_off()).start()
            
            return None
    
    def audio_recording_session(self, duration: int = 10) -> Optional[str]:
        """
        Record audio and save to file.
        
        Args:
            duration: Recording duration in seconds
            
        Returns:
            Filename of recorded audio or None if failed
        """
        if not self.audio:
            logger.error("Audio system not available")
            return None
        
        try:
            logger.info(f"Starting {duration}-second audio recording")
            
            # Visual indication
            if self.led:
                self.led.turn_on()
                self.led.set_color(0, 0, 255)  # Blue for recording
                self.led.set_brightness(60)
            
            # Record audio
            audio_data = self.audio.record_audio(duration=duration)
            
            # Save recording
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.wav"
            self.audio.save_audio_to_file(audio_data, filename)
            
            logger.info(f"Audio recording saved as {filename}")
            
            # Success indication
            if self.led:
                self.led.set_color(0, 255, 0)  # Green for success
                threading.Timer(2.0, lambda: self.led.turn_off()).start()
            
            return filename
            
        except Exception as e:
            logger.error(f"Error during audio recording: {e}")
            
            # Error indication
            if self.led:
                self.led.set_color(255, 0, 0)  # Red for error
                threading.Timer(3.0, lambda: self.led.turn_off()).start()
            
            return None
    
    def system_status_display(self) -> None:
        """Display system status on e-ink screen."""
        if not self.display:
            logger.error("Display not available for status")
            return
        
        try:
            # This would typically generate a status image
            # For now, just clear the display
            self.display.clear_display()
            logger.info("System status displayed")
            
        except Exception as e:
            logger.error(f"Error displaying system status: {e}")
    
    def get_hardware_status(self) -> Dict[str, Any]:
        """Get hardware status."""
        return {
            "system_status": self.status.value,
            "hardware_state": {
                "audio": self.hardware_state.audio_initialized,
                "camera": self.hardware_state.camera_initialized,
                "display": self.hardware_state.display_initialized,
                "led": self.hardware_state.led_initialized,
            },
            "last_error": self.hardware_state.last_error,
            "timestamp": time.time()
        }
    
    def cleanup(self) -> None:
        """Clean up all hardware resources."""
        logger.info("Cleaning up MCP hub resources")
        
        self.status = SystemStatus.SHUTDOWN
        self.shutdown_event.set()
        
        if self.led:
            try:
                self.led.turn_off()
            except Exception as e:
                logger.error(f"Error cleaning up LED: {e}")
        
        if self.display:
            try:
                self.display.clear_display()
                self.display.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up display: {e}")
        
        if self.camera:
            try:
                self.camera.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up camera: {e}")
        
        if self.audio:
            try:
                # Audio cleanup if available
                pass
            except Exception as e:
                logger.error(f"Error cleaning up audio: {e}")
        
        logger.info("MCP hub cleanup completed")

def main():
    """Main entry point for MCP hub demo."""
    hub = None
    
    try:
        # Initialize hub
        hub = MCPHub()
        
        if hub.status == SystemStatus.ERROR:
            logger.error("Failed to initialize MCP hub")
            return 1
        
        # Demonstrate functionality
        logger.info("Running MCP hub demonstration")
        
        # Display system status
        hub.system_status_display()
        time.sleep(2)
        
        # Capture and display image
        image = hub.capture_and_display()
        if image:
            logger.info("Image capture successful")
        
        time.sleep(3)
        
        # Audio recording session
        audio_file = hub.audio_recording_session(duration=5)
        if audio_file:
            logger.info(f"Audio recording successful: {audio_file}")
        
        # Print final status
        status = hub.get_hardware_status()
        logger.info(f"Final system status: {status}")
        
    except Exception as e:
        logger.error(f"MCP hub demo failed: {e}")
        return 1
    
    finally:
        if hub:
            hub.cleanup()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

## Migration Guide (v0.2.0)

### E-ink Display Updates

The e-ink module has been significantly enhanced with new features while maintaining full backward compatibility:

#### What's New
- **Multi-format support**: Display JPEG, BMP, TIFF, WebP, and more
- **Image caching**: Automatic caching with persistence
- **Rust processing**: 2-3x faster image conversion
- **Better API**: New `Display` class with enhanced features

#### Migration Examples

**Old Code (Still Works):**
```python
from distiller_cm5_sdk.hardware.eink import EinkDriver, load_and_convert_image

display = EinkDriver()
display.initialize()
image_data = load_and_convert_image("image.png")
display.display_image(image_data)
```

**New Code (Recommended):**
```python
from distiller_cm5_sdk.hardware.eink import Display, display_image_auto

# Simple one-liner for any format
display_image_auto("image.jpg")  # Works with JPEG, PNG, BMP, TIFF, etc.

# Or with Display class for more control
with Display() as display:
    display.display_image_auto("photo.webp")  # Any format!
    stats = Display.get_cache_stats()  # Check cache performance
```

#### Key Improvements
- **No manual conversion needed**: Automatic format detection and conversion
- **Format agnostic**: Same API for PNG, JPEG, BMP, TIFF, WebP, etc.
- **Performance boost**: Caching eliminates repeated conversions
- **Cleaner API**: Context managers and convenience functions

## Version Information

- **SDK Version:** 0.2.0
- **Python Version:** 3.11+
- **uv Version:** Latest (auto-installed)
- **Build System:** Debian packaging with uv
- **Compatible Platforms:** ARM64 Linux (CM5 platform)
- **License:** See LICENSE file

## Contributing

### Development Setup

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/distiller-cm5-sdk.git`
3. Create a development branch: `git checkout -b feature/your-feature`
4. Make your changes following the coding standards
5. Test thoroughly with the debian package build
6. Commit with clear messages: `git commit -m "Add: your feature description"`
7. Push to your fork: `git push origin feature/your-feature`
8. Submit a pull request with detailed description

### Code Standards

- Follow PEP 8 for Python code formatting
- Include comprehensive error handling and logging
- Add type hints for all function signatures
- Write docstrings for all public functions and classes
- Include unit tests for new functionality
- Update documentation for any API changes

### Testing

```bash
# Run the build process
./build.sh

# Build and test the package
./build-deb.sh

# Install and test locally
sudo dpkg -i dist/distiller-cm5-sdk_*_arm64.deb
sudo apt-get install -f

# Run comprehensive tests
python -m pytest tests/ -v
```

### Reporting Issues

When reporting issues, please include:
- System information (OS, hardware platform)
- SDK version and installation method
- Complete error messages and stack traces
- Steps to reproduce the issue
- Expected vs actual behavior

## License

This project is licensed under the terms specified in the `LICENSE` file.

---

For more information and support, visit the [Distiller CM5 SDK GitHub repository](https://github.com/Pamir-AI/distiller-cm5-sdk).

