# E-ink Composer Module

A powerful layer-based composition system for creating sophisticated e-ink displays with text, images, and graphics. Built on top of the Distiller CM5 SDK's high-performance Rust backend.

> **Note**: The composer now supports automatic display dimension detection and improved resource management. Some methods shown in examples like `clear_layers()` and `move_layer_to_top()` are planned features - use individual layer operations for now.

## 🎨 What is Composer?

Composer transforms e-ink displays from simple image viewers into dynamic, multi-layered canvases. Think of it as Photoshop for e-ink - stack layers, apply transformations, and create complex layouts programmatically or visually.

```python
# Create a weather dashboard in 5 lines
composer = EinkComposer()
composer.add_image_layer("icon", "weather/sunny.png", x=10, y=10)
composer.add_text_layer("temp", "72°F", x=80, y=25, font_size=2)
composer.add_text_layer("conditions", "Partly Cloudy", x=10, y=100)
composer.display()  # Show on e-ink hardware
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│            Application Layer                     │
│  • Templates • Web UI • CLI • Python API         │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────┴────────────────────────────────┐
│           Composer Core                          │
│  • Layer Management • Rendering Pipeline         │
│  • Transform Engine • Template Processing        │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────┴────────────────────────────────┐
│         Hardware Abstraction                     │
│  • Display Driver • Image Processing (Rust)      │
│  • Dithering Engine • Format Conversion          │
└─────────────────────────────────────────────────┘
```

## Core Features

### 🔲 Layer System

Build complex displays by stacking independent layers:

```python
from distiller_cm5_sdk.hardware.eink.composer import EinkComposer

composer = EinkComposer(240, 416)  # High-res display

# Background layer
composer.add_rectangle_layer(
    "background",
    x=0, y=0, width=240, height=416,
    filled=True, color=255  # White background
)

# Logo layer with transformations
composer.add_image_layer(
    "logo",
    "assets/logo.png",
    x=10, y=10,
    resize_mode="fit",      # Maintain aspect ratio
    dither_mode="floyd-steinberg",
    brightness=1.1,         # Slight brightness boost
    rotate=0,               # No rotation
    flip_h=False           # No horizontal flip
)

# Dynamic text overlay
composer.add_text_layer(
    "status",
    "System Online",
    x=10, y=380,
    color=0,               # Black text
    font_size=2,          # Double size
    background=True,      # White background box
    padding=5            # 5px padding around text
)

# Render and display
composer.render()  # Creates final image
composer.display() # Show on hardware
```

### 📝 Advanced Text Rendering

High-quality bitmap font with extensive customization:

```python
from distiller_cm5_sdk.hardware.eink.composer import measure_text

# Measure text dimensions for perfect alignment
width, height = measure_text("Hello World", font_size=2)

# Add centered text
composer.add_text_layer(
    "title",
    "DASHBOARD",
    x=(240 - width) // 2,  # Center horizontally
    y=20,
    font_size=2,
    rotate=0,              # Rotation: 0, 90, 180, 270
    flip_h=False,          # Horizontal flip
    flip_v=False,          # Vertical flip
    background=True,       # Background rectangle
    padding=10            # Padding around text
)

# Multi-line text
lines = ["Line 1", "Line 2", "Line 3"]
y_offset = 50
for i, line in enumerate(lines):
    composer.add_text_layer(
        f"line_{i}",
        line,
        x=10,
        y=y_offset + (i * 20),  # 20px line height
        color=0
    )
```

### 🖼️ Smart Image Processing

Leverages Rust backend for blazing-fast image operations:

```python
# Advanced image layer with all options
composer.add_image_layer(
    layer_id="photo",
    image_path="landscape.jpg",
    x=0, y=50,
    width=240, height=200,     # Target dimensions
    resize_mode="crop",        # crop, fit, or stretch
    dither_mode="sierra",      # Multiple dithering algorithms
    brightness=1.2,            # 20% brighter
    contrast=0.1,              # Slight contrast boost
    rotate=90,                 # 90° rotation
    flip_h=True,              # Mirror horizontally
    crop_x=100, crop_y=50     # Custom crop position
)

# Dithering options for optimal quality
dither_modes = [
    "none",           # Simple threshold
    "floyd-steinberg", # High quality (default)
    "sierra",         # Good quality, faster
    "sierra-2row",    # Balanced
    "sierra-lite",    # Fast
    "simple",         # Legacy threshold
    "threshold"       # Alias for simple
]
```

### 🎯 Layer Management

Fine-grained control over composition:

```python
# Create and manipulate layers
composer = EinkComposer()

# Add multiple layers
composer.add_text_layer("title", "Dashboard", x=10, y=10)
composer.add_image_layer("graph", "chart.png", x=10, y=40)
composer.add_rectangle_layer("border", x=0, y=0, width=128, height=250, filled=False)

# Get layer information
layers = composer.get_layer_info()
for layer in layers:
    print(f"Layer {layer['id']}: {layer['type']} at ({layer['x']}, {layer['y']})")

# Toggle visibility
composer.set_layer_visibility("graph", False)

# Remove layer
composer.remove_layer("title")

# Toggle layer visibility
composer.toggle_layer("border")

# Update layer properties
composer.update_layer("title", x=20, y=30)

# Get layer information
layers = composer.get_layer_info()
```

## Template System

Create reusable, data-driven displays with JSON templates:

### Template Structure

```json
{
    "name": "Weather Dashboard",
    "width": 240,
    "height": 416,
    "layers": [
        {
            "id": "temperature",
            "type": "text",
            "text": "{{temperature}}°F",
            "x": 50,
            "y": 100,
            "font_size": 3,
            "color": 0
        },
        {
            "id": "icon",
            "type": "image",
            "image_path": "icons/{{weather_condition}}.png",
            "x": 10,
            "y": 10,
            "resize_mode": "fit"
        },
        {
            "id": "qr_code",
            "type": "qr_placeholder",
            "data": "{{device_url}}",
            "x": 150,
            "y": 300,
            "size": [80, 80]
        }
    ]
}
```

### Using Templates

```python
from distiller_cm5_sdk.hardware.eink.composer.templates import TemplateRenderer

# Load template
renderer = TemplateRenderer("templates/weather/template.json")

# Render with dynamic data
composer = renderer.render(
    temperature="72",
    weather_condition="sunny",
    device_url="https://device.local:8080",
    humidity="45%",
    wind_speed="12 mph"
)

# Display result
composer.display()

# Or save to file
composer.save("weather_display.png")
```

### QR Code Generation

Templates support automatic QR code generation:

```python
# Template with QR placeholder
template = {
    "layers": [{
        "type": "qr_placeholder",
        "data": "{{wifi_password}}",
        "size": [100, 100],
        "error_correction": "M"  # L, M, Q, or H
    }]
}

# Generates QR code automatically
composer = create_template_from_dict(template, wifi_password="MySecureWiFi123")
```

## CLI Interface

Powerful command-line tools for scripting and automation:

### Session Management

```bash
# Create new composition
eink-compose create --size 240x416

# Resume previous session
eink-compose list  # Shows current layers

# Clear session
eink-compose clear
```

### Layer Operations

```bash
# Add text layer
eink-compose add-text status "System Ready" --x 10 --y 10 --font-size 2

# Add image with transformations
eink-compose add-image logo logo.png \
    --x 50 --y 50 \
    --resize-mode fit \
    --dither floyd-steinberg \
    --rotate 90 \
    --brightness 1.2

# Add rectangle
eink-compose add-rect frame \
    --x 0 --y 0 \
    --width 240 --height 416 \
    --filled false \
    --border-width 3

# Remove layer
eink-compose remove status

# Toggle visibility
eink-compose toggle logo
```

### Rendering and Display

```bash
# Preview composition
eink-compose render --output preview.png

# Display on hardware
eink-compose display --mode full

# Use partial refresh for updates
eink-compose display --mode partial

# Export as different formats
eink-compose render --output display.bmp --format bmp
eink-compose render --output display.raw --format raw
```

### Template Usage

```bash
# Render template with data
eink-compose template weather.json \
    --data temperature=72 \
    --data condition=sunny \
    --output weather.png

# Display template directly
eink-compose template-display dashboard.json \
    --data ip_address=192.168.1.100 \
    --data status=online
```

## Web Interface

Browser-based visual editor for interactive composition:

### Starting the Server

```python
from distiller_cm5_sdk.hardware.eink.composer.web_app import app

# Run with default settings
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
```

Or via command line:
```bash
python -m distiller_cm5_sdk.hardware.eink.composer.run_web
```

### Features

- **Visual Layer Editor**: Drag-and-drop interface
- **Live Preview**: Real-time composition preview
- **Property Panel**: Adjust all layer properties
- **Template Editor**: Create and test templates
- **Hardware Control**: Display directly from browser
- **Export Options**: Save as PNG, BMP, or raw data

### API Endpoints

```python
# GET endpoints
/api/layers          # List all layers
/api/preview         # Get current preview
/api/templates       # List available templates

# POST endpoints
/api/layers/text     # Add text layer
/api/layers/image    # Add image layer
/api/layers/rect     # Add rectangle layer
/api/render          # Render composition
/api/display         # Show on hardware

# DELETE endpoints
/api/layers/<id>     # Remove layer
/api/clear           # Clear all layers
```

## Performance Optimization

### Rust-Powered Processing

The composer leverages the SDK's Rust backend for superior performance:

| Operation | Python (PIL) | Rust Backend | Improvement |
|-----------|-------------|--------------|-------------|
| Image Load | 150ms | 45ms | 3.3x |
| Floyd-Steinberg | 95ms | 18ms | 5.3x |
| Scaling | 80ms | 25ms | 3.2x |
| Rotation | 60ms | 20ms | 3.0x |
| Full Render | 400ms | 120ms | 3.3x |

### Optimization Tips

```python
# Pre-process images for faster rendering
from PIL import Image

def optimize_image(path):
    img = Image.open(path)
    # Convert to grayscale
    img = img.convert('L')
    # Resize to target dimensions
    img = img.resize((240, 416), Image.LANCZOS)
    # Save optimized version
    img.save(f"optimized_{path}")
    return f"optimized_{path}"

# Use optimized images in composer
composer.add_image_layer("photo", optimize_image("large_photo.jpg"))

# Batch operations for efficiency
layers = [
    ("text", "title", {"text": "Dashboard", "x": 10, "y": 10}),
    ("image", "logo", {"image_path": "logo.png", "x": 200, "y": 10}),
    ("rect", "border", {"width": 240, "height": 416, "filled": False})
]

for layer_type, layer_id, props in layers:
    if layer_type == "text":
        composer.add_text_layer(layer_id, **props)
    elif layer_type == "image":
        composer.add_image_layer(layer_id, **props)
    elif layer_type == "rect":
        composer.add_rectangle_layer(layer_id, **props)
```

## Advanced Examples

### Information Dashboard

```python
def create_dashboard(data):
    composer = EinkComposer(240, 416)
    
    # Header
    composer.add_rectangle_layer("header_bg", 0, 0, 240, 60, True, 0)
    composer.add_text_layer(
        "title", "SYSTEM STATUS",
        x=10, y=20, color=255, font_size=2
    )
    
    # Status indicators
    y_pos = 80
    for service, status in data['services'].items():
        color = 0 if status == 'OK' else 255
        bg = 255 if status == 'OK' else 0
        
        composer.add_rectangle_layer(
            f"{service}_bg",
            10, y_pos, 220, 30, True, bg
        )
        composer.add_text_layer(
            service,
            f"{service}: {status}",
            x=15, y=y_pos + 10, color=color
        )
        y_pos += 40
    
    # Graph
    composer.add_image_layer(
        "graph", "performance_graph.png",
        x=10, y=280, width=220, height=120,
        resize_mode="stretch"
    )
    
    return composer
```

### Menu System

```python
class MenuComposer:
    def __init__(self, items, selected_index=0):
        self.composer = EinkComposer(128, 250)
        self.items = items
        self.selected = selected_index
        self.render_menu()
    
    def render_menu(self):
        # Create fresh composer for clean render
        self.composer = EinkComposer(128, 250)
        
        # Title
        self.composer.add_text_layer(
            "title", "MENU",
            x=40, y=10, font_size=2
        )
        
        # Menu items
        y_pos = 40
        for i, item in enumerate(self.items):
            if i == self.selected:
                # Highlight selected
                self.composer.add_rectangle_layer(
                    f"sel_{i}", 0, y_pos-2, 128, 20, True, 0
                )
                color = 255
            else:
                color = 0
            
            self.composer.add_text_layer(
                f"item_{i}", f"  {item}",
                x=5, y=y_pos, color=color
            )
            y_pos += 25
    
    def move_selection(self, direction):
        self.selected = (self.selected + direction) % len(self.items)
        self.render_menu()
        # Display with partial refresh for fast updates
        from distiller_cm5_sdk.hardware.eink import DisplayMode
        self.composer.display(mode=DisplayMode.PARTIAL)
```

### Live Data Display

```python
import asyncio
from datetime import datetime

async def live_clock():
    composer = EinkComposer(128, 250)
    
    while True:
        # Create fresh composer for each update
        composer = EinkComposer(128, 250)
        
        # Current time
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%Y-%m-%d")
        
        # Time display
        composer.add_text_layer(
            "time", time_str,
            x=20, y=100, font_size=2
        )
        
        # Date display
        composer.add_text_layer(
            "date", date_str,
            x=25, y=130
        )
        
        # Update display with partial refresh
        from distiller_cm5_sdk.hardware.eink import DisplayMode
        composer.display(mode=DisplayMode.PARTIAL)
        
        await asyncio.sleep(1)

# Run live clock
asyncio.run(live_clock())
```

## Troubleshooting

### Common Issues

**Layer not visible:**
```python
# Check layer exists
print(composer.get_layer_info())

# Toggle visibility
composer.toggle_layer("layer_id")

# Update layer properties
composer.update_layer("layer_id", x=10, y=20)
```

**Image distortion:**
```python
# Use appropriate resize mode
composer.add_image_layer(
    "photo", "image.jpg",
    resize_mode="fit"  # Maintains aspect ratio
)

# Pre-process image
img = Image.open("image.jpg")
img = img.resize((240, 416), Image.LANCZOS)
img.save("processed.jpg")
```

**Slow rendering:**
```python
# Use simpler dithering
composer.add_image_layer(
    "img", "photo.jpg",
    dither_mode="simple"  # Faster than floyd-steinberg
)

# Reduce layer count
# Combine static elements into single image
```

**Memory issues:**
```python
# Clear unused layers
composer.remove_layer("unused_layer")

# Use smaller images
# Convert images to grayscale before loading
```

## API Reference

### EinkComposer Class

```python
class EinkComposer:
    def __init__(self, width: int | None = None, height: int | None = None)
    def add_text_layer(layer_id: str, text: str, **kwargs) -> str
    def add_image_layer(layer_id: str, image_path: str, **kwargs) -> str
    def add_rectangle_layer(layer_id: str, **kwargs) -> str
    def remove_layer(layer_id: str) -> bool
    def update_layer(layer_id: str, **kwargs) -> bool
    def toggle_layer(layer_id: str) -> bool
    def get_layer_info() -> list[dict]
    def render() -> np.ndarray
    def save(filename: str, format: Literal["png", "bmp", "binary"] = "png") -> None
    def display(mode: DisplayMode = DisplayMode.FULL, **kwargs) -> bool
    def clear_display() -> bool
    def save_json(filename: str) -> None
```

### Layer Classes

```python
@dataclass
class TextLayer:
    text: str
    x: int = 0
    y: int = 0
    color: int = 0
    font_size: int = 1
    rotate: int = 0
    flip_h: bool = False
    flip_v: bool = False
    background: bool = False
    padding: int = 2

@dataclass
class ImageLayer:
    image_path: str
    x: int = 0
    y: int = 0
    width: Optional[int] = None
    height: Optional[int] = None
    resize_mode: str = "fit"
    dither_mode: str = "floyd-steinberg"
    brightness: float = 1.0
    contrast: float = 0.0
    rotate: int = 0
    flip_h: bool = False
    flip_v: bool = False

@dataclass
class RectangleLayer:
    x: int = 0
    y: int = 0
    width: int = 10
    height: int = 10
    filled: bool = True
    color: int = 0
    border_width: int = 1
```

## Related Components

- [E-ink Display Module](../): Core display driver and hardware interface
- [Firmware Module](../lib/src/firmware/): Low-level display protocols
- [Examples](examples/): Complete example applications

## License

Part of the Distiller CM5 SDK. See LICENSE file for details.