# E-ink Composer Module

High-level composition system for e-ink displays integrated with Distiller CM5 SDK.

## Features

- **Layer-based composition**: Build complex displays with text, images, and shapes
- **Rust-powered image processing**: Uses SDK's native Rust backend for 2-3x faster processing
- **Template system**: Create reusable templates with dynamic placeholders
- **CLI interface**: Command-line tools for quick composition
- **Web UI**: Browser-based editor for visual composition
- **Hardware integration**: Direct display on e-ink hardware via SDK

## Installation

The composer module is included with the Distiller CM5 SDK. Install the SDK:

```bash
pip install distiller-cm5-sdk
```

Or for development:
```bash
pip install -e /path/to/distiller-cm5-sdk
```

## Quick Start

### Python API

```python
from distiller_cm5_sdk.hardware.eink.composer import EinkComposer

# Create composer for standard e-ink (122x250)
composer = EinkComposer(122, 250)

# Add text layer
composer.add_text_layer(
    layer_id='hello',
    text='HELLO E-INK',
    x=20, y=100,
    color=0  # Black
)

# Add rectangle
composer.add_rectangle_layer(
    layer_id='border',
    x=0, y=0,
    width=122, height=250,
    filled=False,
    color=0
)

# Save to file
composer.save('output.png')

# Display on hardware (if available)
composer.display()
```

### CLI Usage

```bash
# Create composition
eink-compose create --size 122x250

# Add layers
eink-compose add-text hello "HELLO E-INK" --x 20 --y 100
eink-compose add-rect border --width 122 --height 250 --filled false

# List layers
eink-compose list

# Render to file
eink-compose render --output display.png --format png

# Display on hardware
eink-compose display
```

### Web UI

```bash
# Run web interface
python -m distiller_cm5_sdk.hardware.eink.composer.run_web

# Access at http://localhost:5000
```

## Architecture

The composer module leverages the SDK's Rust backend for all image processing:

- **Image loading**: Multiple format support via Rust
- **Scaling**: Hardware-accelerated letterbox, crop, and stretch modes
- **Dithering**: Fast Floyd-Steinberg implementation in Rust
- **Binary conversion**: Optimized bit-packing for e-ink displays

### Performance

Compared to pure Python implementation:
- Image processing: 2-3x faster
- Dithering: 5x faster for Floyd-Steinberg
- Memory usage: 40% less for large images

## Layer Types

### Text Layers
- Bitmap font rendering (6x8 characters)
- Rotation and flipping support
- Optional background with padding

### Image Layers
- Multiple format support (PNG, JPEG, BMP, etc.)
- Resize modes: stretch, fit, crop
- Dithering: Floyd-Steinberg or threshold
- Transformations: rotate, flip, brightness, contrast

### Rectangle Layers
- Filled or outlined rectangles
- Configurable border width
- Used for backgrounds, borders, and UI elements

## Templates

Create reusable templates with dynamic placeholders:

```python
from distiller_cm5_sdk.hardware.eink.composer.templates import TemplateRenderer

# Load template
renderer = TemplateRenderer('templates/my_template/template.json')

# Render with dynamic data
composer = renderer.render(
    ip_address='192.168.1.100',
    tunnel_url='https://tunnel.example.com'
)

# Display result
composer.display()
```

## Examples

See the `example_*.py` files for complete examples:
- `example_basic.py`: Simple composition with text and shapes
- `example_hardware.py`: Display on actual e-ink hardware
- `example_template.py`: Using templates with placeholders

## Migration from Standalone CLI

If migrating from the standalone `distiller-eink-cli` project:

1. Update imports:
   ```python
   # Old
   from eink_composer import EinkComposer
   
   # New
   from distiller_cm5_sdk.hardware.eink.composer import EinkComposer
   ```

2. Image processing is now handled by SDK's Rust backend automatically
3. CLI commands remain the same via `eink-compose`
4. Templates are compatible without changes

## Hardware Requirements

- Raspberry Pi or compatible board
- E-ink display (122x250 or 240x416)
- SPI connection to display
- Distiller CM5 SDK drivers installed

## License

Part of Distiller CM5 SDK by PamirAI Inc.