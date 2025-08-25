# LED Module SDK Documentation

## Overview

The LED module provides **full RGB LED control** for the CM5 device through the Linux sysfs interface. It supports multiple LEDs with individual control of RGB colors, brightness settings, animation modes, and custom LED triggers.

The module wraps the SAM driver's sysfs interface located at `/sys/class/leds/pamir:led*` and provides both a high-level Python API and legacy compatibility with the previous interface.

The module is compatible with SAM protocol v0.2.0 which uses RGB444 internal encoding (4-bit per channel) for efficient communication with the hardware.

## Prerequisites

- The SAM driver must be loaded and create LED devices at `/sys/class/leds/pamir:led*`
- **Root privileges required**: LED control requires write access to sysfs files
- Python 3.6+ with pathlib and subprocess support

### Permission Requirements

The LED sysfs interface requires root privileges for write operations. You have several options:

1. **Use sudo mode** (recommended): Initialize with `LED(use_sudo=True)`
2. **Run as root**: Use `sudo python your_script.py`
3. **Configure udev rules**: Set up permissions for your user (advanced)

## Installation

The LED module is part of the CM5 Linux SDK and can be imported from:

```python
from distiller_cm5_sdk.hardware.sam.led import LED, LEDError, create_led_with_sudo
```

## Quick Start

```python
from distiller_cm5_sdk.hardware.sam.led import LED

# Initialize LED module with sudo mode (recommended)
led = LED(use_sudo=True)

# Get available LEDs
available_leds = led.get_available_leds()
print(f"Available LEDs: {available_leds}")

# Set LED 0 to red
led.set_rgb_color(0, 255, 0, 0)

# Set brightness
led.set_brightness(0, 128)

# Make it blink
led.blink_led(0, 255, 0, 0, timing=500)

# Turn off all LEDs when done
led.turn_off_all()
```

### Alternative: Running as Root

```python
# If running the entire script as root (sudo python script.py)
led = LED(use_sudo=False)  # No need for internal sudo
```

### Quick Setup Function

```python
from distiller_cm5_sdk.hardware.sam.led import create_led_with_sudo

# Convenient function that creates LED with sudo enabled
led = create_led_with_sudo()
```

## Interactive Demo

For a comprehensive demonstration of all LED features, run the interactive demo:

```bash
python led_interactive_demo.py
```

This interactive demo includes:
- 🎯 LED discovery and initialization
- 🎨 RGB color control (primary and secondary colors)
- 💡 Brightness control (multiple levels)
- 🔸 Multi-LED control (different colors and modes on each LED)
- 🎯 Convenience methods and bulk operations
- 🧪 Error handling and validation
- 🔐 Sudo mode management
- ✨ Animation modes (blink, fade, rainbow)
- 🎭 LED triggers (heartbeat-rgb, breathing-rgb, rainbow-rgb)

The demo waits for you to press Enter between each section, so you can see each feature in action.

## Class: LED

### Initialization

```python
led = LED(base_path="/sys/class/leds", use_sudo=False)
```

Parameters:
- `base_path`: Base path for LED sysfs interface (default: `/sys/class/leds`)
- `use_sudo`: Whether to use sudo for write operations (default: `False`)

Raises:
- `LEDError`: If the sysfs interface is not available or no compatible LEDs are found

### Permission Management

#### `set_sudo_mode(use_sudo: bool) -> None`

Enable or disable sudo mode for write operations.

```python
led = LED()  # Start without sudo
led.set_sudo_mode(True)  # Enable sudo mode
# Now all write operations will use sudo
```

### LED Discovery

#### `get_available_leds() -> List[int]`

Get list of available LED IDs.

Returns:
- List of LED numbers (e.g., `[0, 1, 2]` for led0, led1, led2)

Example:
```python
leds = led.get_available_leds()
print(f"Found LEDs: {leds}")  # Output: Found LEDs: [0, 1, 2]
```

### RGB Color Control

#### `set_rgb_color(led_id: int, red: int, green: int, blue: int) -> None`

Set RGB color for a specific LED.

Parameters:
- `led_id`: LED number (0, 1, 2, etc.)
- `red`: Red component (0-255)
- `green`: Green component (0-255)  
- `blue`: Blue component (0-255)

Raises:
- `LEDError`: If LED ID is invalid or color values are out of range

#### `get_rgb_color(led_id: int) -> Tuple[int, int, int]`

Get current RGB color for a specific LED.

Returns:
- Tuple of (red, green, blue) values (0-255)

Example:
```python
# Set LED 0 to purple
led.set_rgb_color(0, 128, 0, 255)

# Read back the color
r, g, b = led.get_rgb_color(0)
print(f"Current color: R={r}, G={g}, B={b}")
```

### Animation Modes

#### `set_animation_mode(led_id: int, mode: str, timing: Optional[int] = None) -> None`

Set animation mode for a specific LED.

Parameters:
- `led_id`: LED number (0, 1, 2, etc.)
- `mode`: Animation mode ('static', 'blink', 'fade', 'rainbow')
- `timing`: Optional timing in milliseconds (100, 200, 500, or 1000)

Supported modes:
- `'static'`: Solid color (0x00)
- `'blink'`: On/off blinking pattern (0x01)
- `'fade'`: Smooth brightness transitions (0x02)
- `'rainbow'`: Full spectrum color cycling (0x03)

Raises:
- `LEDError`: If LED ID is invalid, mode is unknown, or timing is invalid

#### `get_animation_mode(led_id: int) -> Tuple[str, int]`

Get current animation mode and timing for a specific LED.

Returns:
- Tuple of (mode_string, timing_ms)

### LED Triggers

#### `set_trigger(led_id: int, trigger: str) -> None`

Set LED trigger for a specific LED.

Parameters:
- `led_id`: LED number (0, 1, 2, etc.)
- `trigger`: Trigger name ('none', 'heartbeat-rgb', 'breathing-rgb', 'rainbow-rgb')

Available triggers:
- `'none'`: No trigger, manual control
- `'heartbeat-rgb'`: Red heartbeat pattern (double-pulse)
- `'breathing-rgb'`: Blue breathing animation
- `'rainbow-rgb'`: Full spectrum rainbow cycling

Raises:
- `LEDError`: If LED ID is invalid or trigger is not available

#### `get_trigger(led_id: int) -> str`

Get current trigger for a specific LED.

Returns:
- Current trigger name (e.g., 'none', 'heartbeat-rgb')

#### `get_available_triggers(led_id: int) -> List[str]`

Get list of available triggers for a specific LED.

Returns:
- List of available trigger names

### Brightness Control

#### `set_brightness(led_id: int, brightness: int) -> None`

Set overall brightness for a specific LED (preserves RGB ratios).

Parameters:
- `led_id`: LED number (0, 1, 2, etc.)
- `brightness`: Brightness value (0-255)

#### `get_brightness(led_id: int) -> int`

Get current brightness for a specific LED.

Example:
```python
# Set LED to half brightness
led.set_brightness(0, 128)

# Set multiple LEDs to different brightness levels
led.set_brightness(0, 255)  # Full brightness
led.set_brightness(1, 128)  # Half brightness
led.set_brightness(2, 64)   # Quarter brightness
```

## Convenience Methods

### Individual LED Control

#### `static_led(led_id: int, red: int, green: int, blue: int) -> None`

Set LED to static color. (Equivalent to `set_rgb_color()`)

#### `blink_led(led_id: int, red: int, green: int, blue: int, timing: int = 500) -> None`

Set a LED to blink with specified color.

Parameters:
- `led_id`: LED number (0, 1, 2, etc.)
- `red`: Red component (0-255)
- `green`: Green component (0-255)
- `blue`: Blue component (0-255)
- `timing`: Blink timing in milliseconds (100, 200, 500, or 1000)

#### `fade_led(led_id: int, red: int, green: int, blue: int, timing: int = 1000) -> None`

Set a LED to fade with specified color.

Parameters:
- `led_id`: LED number (0, 1, 2, etc.)
- `red`: Red component (0-255)
- `green`: Green component (0-255)
- `blue`: Blue component (0-255)
- `timing`: Fade timing in milliseconds (100, 200, 500, or 1000)

#### `rainbow_led(led_id: int, timing: int = 1000) -> None`

Set a LED to rainbow cycle mode.

Parameters:
- `led_id`: LED number (0, 1, 2, etc.)
- `timing`: Rainbow cycle timing in milliseconds (100, 200, 500, or 1000)

#### `turn_off(led_id: int) -> None`

Turn off a specific LED.

### Bulk Operations

#### `set_color_all(red: int, green: int, blue: int) -> None`

Set the same RGB color for all available LEDs.

#### `set_brightness_all(brightness: int) -> None`

Set the same brightness for all available LEDs.

#### `turn_off_all() -> None`

Turn off all available LEDs.

Example:
```python
# Convenience methods for static operations
led.static_led(0, 255, 0, 0)          # Static red on LED 0
led.set_rgb_color(1, 0, 255, 0)       # Direct green on LED 1  
led.set_rgb_color(2, 0, 0, 255)       # Direct blue on LED 2

# Bulk operations
led.set_color_all(255, 255, 255)      # All LEDs white
led.set_brightness_all(100)           # All LEDs dimmed
led.turn_off_all()                    # Turn off everything

# Animation methods are fully supported
led.blink_led(0, 255, 0, 0)           # ✅ Blinking red
led.fade_led(0, 0, 255, 0)            # ✅ Fading green  
led.rainbow_led(0)                    # ✅ Rainbow cycle
```

## Legacy Compatibility

The module provides backward compatibility with the previous interface:

#### `connect() -> bool`

Legacy compatibility method (always returns True).

#### `disconnect() -> None`

Legacy compatibility method (no operation).

#### `set_led_color(r: int, g: int, b: int, brightness: float = 0.5, delay: float = 0.0, led_id: int = 0) -> bool`

Legacy method for setting LED color with 0.0-1.0 brightness scale.

Example:
```python
# Legacy usage (still supported)
result = led.set_led_color(255, 128, 0, brightness=0.7, led_id=0)
```

## Error Handling

The LED module uses custom `LEDError` exceptions for all LED-related errors:

```python
from distiller_cm5_sdk.hardware.sam.led import LED, LEDError

try:
    led = LED()
    led.set_rgb_color(0, 255, 0, 0)
except LEDError as e:
    print(f"LED Error: {e}")
    # Handle specific LED errors
except Exception as e:
    print(f"Unexpected error: {e}")
```

Common error scenarios:
- **Initialization**: No LEDs found, sysfs interface unavailable
- **Invalid LED ID**: Attempting to control non-existent LED
- **Invalid values**: RGB values outside 0-255 range, brightness outside 0-255 range
- **Invalid modes**: Unsupported animation modes or triggers
- **Invalid timing**: Animation timing outside 100-1600ms range
- **Permission errors**: Insufficient permissions to write to sysfs files

## Constants and Validation

### Animation Modes
Supported animation modes:
- `'static'` (0x00): Solid color, no animation
- `'blink'` (0x01): On/off blinking pattern
- `'fade'` (0x02): Smooth brightness transitions
- `'rainbow'` (0x03): Full spectrum color cycling

### Triggers
Available LED triggers:
- `'none'`: No trigger, manual control
- `'heartbeat-rgb'`: Red heartbeat pattern
- `'breathing-rgb'`: Blue breathing animation
- `'rainbow-rgb'`: Rainbow color cycling

### Timing Constraints
Animation timing values (2-bit encoded):
- 100ms (0x00): Fast animations
- 200ms (0x01): Quick animations
- 500ms (0x02): Moderate speed
- 1000ms (0x03): Slow animations

### Value Ranges
- RGB components: 0-255
- Brightness: 0-255
- LED IDs: Must be in available LEDs list

## Multi-LED Support

The module supports multiple independent LEDs:

```python
# Control different LEDs independently
led.set_rgb_color(0, 255, 0, 0)      # LED 0: Red
led.set_rgb_color(1, 0, 255, 0)      # LED 1: Green  
led.set_rgb_color(2, 0, 0, 255)      # LED 2: Blue

# Different animation modes (fully supported)
led.blink_led(0, 255, 0, 0, 500)     # LED 0: Blinking red
led.fade_led(1, 0, 255, 0, 500)      # LED 1: Fading green (500ms timing)
led.rainbow_led(2, 1000)             # LED 2: Rainbow cycle

# Different triggers (fully supported)
led.set_trigger(0, "heartbeat-rgb")   # LED 0: Heartbeat
led.set_trigger(1, "breathing-rgb")   # LED 1: Breathing
led.set_trigger(2, "none")            # LED 2: No trigger
```

## Complete Example

```python
import time
from distiller_cm5_sdk.hardware.sam.led import LED, LEDError

try:
    # Initialize LED module with sudo mode
    led = LED(use_sudo=True)
    print(f"Available LEDs: {led.get_available_leds()}")
    
    # Demo RGB color control
    print("RGB Color Demo...")
    colors = [
        (255, 0, 0, "Red"),
        (0, 255, 0, "Green"), 
        (0, 0, 255, "Blue"),
        (255, 255, 0, "Yellow"),
        (255, 0, 255, "Magenta"),
        (0, 255, 255, "Cyan"),
    ]
    
    for r, g, b, name in colors:
        print(f"Setting LED 0 to {name}")
        led.set_rgb_color(0, r, g, b)
        led.set_brightness(0, 200)
        time.sleep(1)
    
    # Demo animation modes
    print("Animation Demo...")
    led.blink_led(0, 255, 0, 0, 400)     # Blinking red
    time.sleep(3)
    
    led.fade_led(0, 0, 0, 255, 800)      # Fading blue
    time.sleep(4)
    
    led.rainbow_led(0, 600)              # Rainbow cycle
    time.sleep(4)
    
    # Demo triggers
    print("Trigger Demo...")
    led.set_trigger(0, "heartbeat-rgb")
    time.sleep(3)
    
    led.set_trigger(0, "breathing-rgb")
    time.sleep(3)
    
    # Cleanup
    led.set_trigger(0, "none")
    led.turn_off_all()
    print("Demo complete!")

except LEDError as e:
    print(f"LED Error: {e}")
    print("Ensure the SAM driver is loaded and LED sysfs interface is available")
except KeyboardInterrupt:
    print("Demo interrupted")
    if 'led' in locals():
        led.turn_off_all()
except Exception as e:
    print(f"Unexpected error: {e}")
finally:
    # Always cleanup
    if 'led' in locals():
        try:
            led.turn_off_all()
        except:
            pass
```

## Troubleshooting

### Driver Not Loaded
```
LEDError: LED sysfs interface not found at /sys/class/leds
```
- Ensure the SAM driver is loaded: `lsmod | grep pamir`
- Check for LED devices: `ls /sys/class/leds/pamir:led*`

### No LEDs Found
```
LEDError: No compatible LEDs found (pamir:led* pattern)
```
- Verify LED devices exist: `ls /sys/class/leds/`
- Check device naming matches `pamir:led*` pattern

### Permission Denied
```
LEDError: Permission denied writing to /sys/class/leds/pamir:led0/red. Try running with sudo or initialize LED(use_sudo=True).
```
**Solutions:**
- Use sudo mode: `led = LED(use_sudo=True)`
- Run entire script with sudo: `sudo python script.py`
- Set up udev rules for user access (advanced)

**Testing your setup:**
```python
# Test if you need sudo
try:
    led = LED(use_sudo=False)
    led.set_rgb_color(0, 255, 0, 0)  # Will fail if permissions needed
except LEDError as e:
    if "Permission denied" in str(e):
        print("Need sudo - reinitializing with sudo mode")
        led = LED(use_sudo=True)
```

### Invalid LED ID
```
LEDError: LED 5 not available. Available LEDs: [0, 1, 2]
```
- Use `get_available_leds()` to check available LED IDs
- Ensure LED ID exists before attempting control

## Performance Notes

- sysfs operations are fast but not real-time
- Multiple LED operations are independent and can be parallelized
- Animation timing is handled by the kernel driver, not userspace
- Reading sysfs values involves file I/O overhead
- For high-frequency updates, consider grouping operations 
