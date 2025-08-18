# E-ink Display Module

A high-performance, production-ready e-ink display driver for ARM64 Linux devices, featuring a hybrid Python-Rust architecture optimized for Raspberry Pi CM5 and Distiller hardware.

## 🚀 Quick Start

```python
from distiller_cm5_sdk.hardware.eink import Display, display_image_auto

# The simplest way - just display an image
display_image_auto("/path/to/image.png")

# Or with more control
display = Display()
display.show_image("photo.jpg", dithering="floyd-steinberg")
display.clear()
```

## Architecture Overview

This module implements a sophisticated dual-layer architecture:

```
┌─────────────────────────────────────────────────────┐
│                  Python Layer                        │
│  • High-level API                                    │
│  • Image processing & caching                        │
│  • Native dithering algorithms                       │
└────────────────┬────────────────────────────────────┘
                 │ ctypes FFI
┌────────────────┴────────────────────────────────────┐
│                   Rust Layer                         │
│  • Hardware abstraction (SPI/GPIO)                   │
│  • Display firmware protocols                        │
│  • Real-time command sequencing                      │
└─────────────────────────────────────────────────────┘
```

The Rust layer provides deterministic, real-time control over the hardware, while Python handles high-level image processing and provides an intuitive API.

## Core Components

### Display Class

The main interface for controlling e-ink displays:

```python
from distiller_cm5_sdk.hardware.eink import Display, DisplayMode, DitheringMethod

display = Display(auto_init=True)  # Auto-detects firmware type

# Display an image with advanced options
display.show_image(
    "artwork.png",
    mode=DisplayMode.PARTIAL,        # Fast partial refresh
    dithering=DitheringMethod.SIERRA,  # High-quality dithering
    rotation=90,                      # Rotate 90° clockwise
    scaling="letterbox",              # Preserve aspect ratio
    brightness=1.2,                   # Slight brightness boost
    contrast=0.1                      # Subtle contrast enhancement
)

# Get display information
info = display.get_info()
print(f"Display: {info['width']}x{info['height']} - {info['firmware']}")

# Capture current display content
display.capture_display("screenshot.png")
```

### Display Modes

Two refresh modes optimize for different use cases:

- **FULL (0)**: Complete refresh with ghosting elimination. Use for high-quality static content.
- **PARTIAL (1)**: Fast updates preserving previous content. Perfect for dynamic UIs.

```python
# High-quality photo display
display.show_image("photo.jpg", mode=DisplayMode.FULL)

# Fast UI updates
for frame in animation_frames:
    display.show_image(frame, mode=DisplayMode.PARTIAL)
```

### Firmware Types

Automatic detection and configuration for multiple display variants:

```python
from distiller_cm5_sdk.hardware.eink import FirmwareType, set_default_firmware

# Check current firmware
current = get_default_firmware()
print(f"Using: {current}")  # e.g., "EPD240x416"

# Switch firmware type (persists across sessions)
set_default_firmware(FirmwareType.EPD240x416)

# Or use environment variable
# export DISTILLER_EINK_FIRMWARE="EPD240x416"
```

**Supported Displays:**
- **EPD128x250**: 128×250 pixels, classic e-reader format
- **EPD240x416**: 240×416 pixels, high-resolution widescreen

## Advanced Image Processing

### Dithering Methods

Transform continuous-tone images into stunning 1-bit displays:

```python
from distiller_cm5_sdk.hardware.eink import DitheringMethod

methods = [
    DitheringMethod.NONE,           # Simple threshold at 50%
    DitheringMethod.FLOYD_STEINBERG, # Classic, high quality
    DitheringMethod.SIERRA,          # 3-row error diffusion
    DitheringMethod.SIERRA_2ROW,     # Faster, good quality
    DitheringMethod.SIERRA_LITE,     # Fastest error diffusion
    DitheringMethod.SIMPLE           # Legacy threshold method
]

# Compare dithering quality
for method in methods:
    display.show_image("gradient.png", dithering=method)
    time.sleep(2)
```

**Performance Comparison:**
| Method | Quality | Speed | Use Case |
|--------|---------|-------|----------|
| Floyd-Steinberg | ★★★★★ | ★★☆☆☆ | Photos, artwork |
| Sierra | ★★★★☆ | ★★★☆☆ | Balanced quality/speed |
| Sierra-2Row | ★★★☆☆ | ★★★★☆ | Real-time rendering |
| Sierra-Lite | ★★☆☆☆ | ★★★★★ | Fast updates |
| None | ★☆☆☆☆ | ★★★★★ | Text, line art |

### Native Dithering Acceleration

When available, the module uses optimized native dithering:

```python
import distiller_cm5_sdk.hardware.eink.dithering as dithering

# Native dithering is 5-10x faster
img_array = np.array(image)
dithered = dithering.floyd_steinberg(img_array, width, height)
```

### Rotation and Transformation

Full transformation pipeline for any orientation:

```python
from distiller_cm5_sdk.hardware.eink import RotationMode

# Rotation modes
display.show_image("photo.jpg", rotation=RotationMode.ROTATE_90)
display.show_image("photo.jpg", rotation=RotationMode.ROTATE_180)
display.show_image("photo.jpg", rotation=RotationMode.ROTATE_270)

# Combined transformations
display.show_image(
    "photo.jpg",
    rotation=90,
    flip_horizontal=True,
    flip_vertical=False
)
```

### Scaling Methods

Intelligent scaling preserves image quality:

```python
from distiller_cm5_sdk.hardware.eink import ScalingMethod

# Letterbox: Maintain aspect ratio with black borders
display.show_image("wide.jpg", scaling=ScalingMethod.LETTERBOX)

# Crop: Center crop to fill display
display.show_image("tall.jpg", scaling=ScalingMethod.CROP_CENTER)

# Stretch: Fill display (may distort)
display.show_image("square.jpg", scaling=ScalingMethod.STRETCH)
```

## Image Caching System

Intelligent caching dramatically improves performance:

```python
from distiller_cm5_sdk.hardware.eink import Display

# Caching is automatic
display = Display(cache_size=100)  # LRU cache for 100 images

# First display: processes and caches
display.show_image("complex.png")  # ~500ms

# Subsequent displays: uses cache
display.show_image("complex.png")  # ~50ms (10x faster!)

# Cache persists across sessions
display = Display(cache_persist_path="/tmp/eink_cache.json")
```

**Cache Performance Metrics:**
- First load: 300-500ms (with dithering)
- Cached load: 30-50ms
- Memory usage: ~100KB per cached image
- Thread-safe implementation with RLock

## Hardware Configuration

### Auto-Detection

The module automatically detects display type on initialization:

```python
# Automatic detection order:
# 1. Environment variable: DISTILLER_EINK_FIRMWARE
# 2. Config file: /opt/distiller-cm5-sdk/eink.conf
# 3. Default: EPD128x250 (backward compatibility)

from distiller_cm5_sdk.hardware.eink import initialize_display_config

# Force re-detection
initialize_display_config()
```

### Manual Configuration

For explicit control:

```python
# Method 1: Environment variable (highest priority)
os.environ["DISTILLER_EINK_FIRMWARE"] = "EPD240x416"

# Method 2: Config file
with open("/opt/distiller-cm5-sdk/eink.conf", "w") as f:
    f.write("EPD240x416")

# Method 3: Programmatic
from distiller_cm5_sdk.hardware.eink import set_default_firmware, FirmwareType
set_default_firmware(FirmwareType.EPD240x416)
```

## Performance Optimization

### Batch Operations

Minimize overhead with batch processing:

```python
# Inefficient: Multiple initializations
for image in images:
    display = Display()
    display.show_image(image)
    
# Efficient: Reuse display instance
display = Display()
for image in images:
    display.show_image(image, mode=DisplayMode.PARTIAL)
```

### Partial Updates

Use partial refresh for responsive UIs:

```python
# Full refresh: 2-3 seconds
display.show_image("menu.png", mode=DisplayMode.FULL)

# Partial refresh: 200-300ms (10x faster!)
display.show_image("menu_selected.png", mode=DisplayMode.PARTIAL)
```

### Pre-Processing Pipeline

Optimize images before display:

```python
def optimize_for_eink(image_path):
    """Pre-process images for optimal display."""
    img = Image.open(image_path)
    
    # Convert to grayscale
    img = img.convert('L')
    
    # Adjust contrast for e-ink
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    
    # Resize to exact display dimensions
    img = img.resize((display.width, display.height), Image.LANCZOS)
    
    return img

# Pre-processed images display 2-3x faster
optimized = optimize_for_eink("photo.jpg")
display.show_image(optimized, skip_processing=True)
```

## Error Handling

Comprehensive error handling with helpful messages:

```python
from distiller_cm5_sdk.hardware.eink import Display, DisplayError

try:
    display = Display()
    display.show_image("image.png")
except DisplayError as e:
    print(f"Display error: {e}")
    # Specific error types:
    # - Initialization failed
    # - Invalid image format
    # - Hardware communication error
    # - Firmware mismatch
except FileNotFoundError:
    print("Image file not found")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Thread Safety

The display module is thread-safe for concurrent access:

```python
import threading

display = Display()
lock = threading.Lock()

def update_region(region_image):
    with lock:
        display.show_image(region_image, mode=DisplayMode.PARTIAL)

# Safe concurrent updates
threads = []
for region in regions:
    t = threading.Thread(target=update_region, args=(region,))
    threads.append(t)
    t.start()
```

## Testing

Comprehensive test utilities included:

```python
# Run hardware tests
python -m distiller_cm5_sdk.hardware.eink._display_test

# Test patterns
from distiller_cm5_sdk.hardware.eink._display_test import (
    create_checkerboard_pattern,
    create_vertical_stripes,
    create_gradient_pattern
)

# Display test patterns
display.show_image(create_checkerboard_pattern(128, 250))
display.show_image(create_gradient_pattern(128, 250))
```

## Troubleshooting

### Common Issues

**Display not responding:**
```python
# Check SPI device
ls /dev/spidev0.0  # Should exist

# Verify GPIO access
groups  # Should include 'gpio' group

# Test with minimal config
display = Display(auto_init=False)
display.initialize()
```

**Image appears distorted:**
```python
# Verify firmware type matches hardware
info = get_display_info()
print(f"Expected: EPD240x416, Got: {info['firmware']}")

# Force correct firmware
set_default_firmware(FirmwareType.EPD240x416)
```

**Slow refresh rates:**
```python
# Use partial refresh for speed
display.show_image("ui.png", mode=DisplayMode.PARTIAL)

# Enable caching
display = Display(cache_size=200)

# Pre-process images
img = Image.open("photo.jpg").convert('L')
display.show_image(img)
```

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

display = Display()
# Now shows detailed SPI communication and timing
```

## Integration Examples

### Photo Frame Application

```python
from pathlib import Path
import time

def photo_frame(photo_dir, interval=30):
    display = Display()
    photos = list(Path(photo_dir).glob("*.jpg"))
    
    while True:
        for photo in photos:
            display.show_image(
                str(photo),
                mode=DisplayMode.FULL,
                dithering=DitheringMethod.FLOYD_STEINBERG,
                scaling=ScalingMethod.LETTERBOX
            )
            time.sleep(interval)
```

### Weather Display

```python
def weather_dashboard(weather_data):
    display = Display()
    composer = EinkComposer(display.width, display.height)
    
    # Add weather icon
    composer.add_image_layer(
        "icon", 
        f"icons/{weather_data['condition']}.png",
        x=10, y=10, width=64, height=64
    )
    
    # Add temperature
    composer.add_text_layer(
        "temp",
        f"{weather_data['temp']}°C",
        x=80, y=30, font_size=2
    )
    
    # Render and display
    image = composer.render()
    display.show_image(image, mode=DisplayMode.PARTIAL)
```

## Performance Benchmarks

Measured on Raspberry Pi CM5:

| Operation | Time | Notes |
|-----------|------|-------|
| Full refresh | 2.1s | Complete ghosting elimination |
| Partial refresh | 0.2s | Fast UI updates |
| Floyd-Steinberg dithering | 0.3s | 128x250 image |
| Native dithering | 0.05s | 5-10x faster |
| Cached image load | 0.03s | From LRU cache |
| Raw SPI transfer | 0.02s | Hardware limit |

## API Reference

See the [API Documentation](https://github.com/distiller/cm5-sdk/docs/eink) for complete reference.

## Related Components

- [Composer Module](composer/): Layer-based composition system
- [Firmware Module](lib/src/firmware/): Low-level display protocols
- [Web Interface](composer/web_app.py): Browser-based compositor

## License

Part of the Distiller CM5 SDK. See LICENSE file for details.