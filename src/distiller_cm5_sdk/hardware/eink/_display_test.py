#!/usr/bin/env python3
"""
E-ink Display Hardware Test Script for CM5 SDK.
This is a real hardware test that mirrors the Rust test_display.rs functionality.
"""

import os
import sys
import time
from typing import Optional

import numpy as np
from PIL import Image

# Add parent directories to path when running directly
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

from distiller_cm5_sdk.hardware.eink.display import (
    Display,
    DisplayMode,
    DitheringMethod,
    FirmwareType,
    ScalingMethod,
    get_default_firmware,
    get_display_info,
    initialize_display_config,
    set_default_firmware,
)


def create_checkerboard_pattern(width: int, height: int, square_size: int = 16) -> Image.Image:
    """Create a checkerboard pattern for testing."""
    img_array = np.zeros((height, width), dtype=np.uint8)

    for y in range(height):
        for x in range(width):
            checker_x = (x // square_size) % 2
            checker_y = (y // square_size) % 2
            if checker_x == checker_y:
                img_array[y, x] = 255
            else:
                img_array[y, x] = 0

    return Image.fromarray(img_array, mode="L")


def create_vertical_stripes(width: int, height: int, stripe_width: int = 8) -> Image.Image:
    """Create vertical stripes pattern."""
    img_array = np.zeros((height, width), dtype=np.uint8)

    for x in range(width):
        if (x // stripe_width) % 2 == 0:
            img_array[:, x] = 255
        else:
            img_array[:, x] = 0

    return Image.fromarray(img_array, mode="L")


def create_horizontal_stripes(width: int, height: int, stripe_height: int = 8) -> Image.Image:
    """Create horizontal stripes pattern."""
    img_array = np.zeros((height, width), dtype=np.uint8)

    for y in range(height):
        if (y // stripe_height) % 2 == 0:
            img_array[y, :] = 255
        else:
            img_array[y, :] = 0

    return Image.fromarray(img_array, mode="L")


def create_gradient_pattern(width: int, height: int) -> Image.Image:
    """Create a gradient pattern."""
    img_array = np.zeros((height, width), dtype=np.uint8)

    for x in range(width):
        gray_value = int(x * 255 / width)
        img_array[:, x] = gray_value

    return Image.fromarray(img_array, mode="L")


def create_white_image(width: int, height: int) -> bytes:
    """Create a white image (all bits set to 1)."""
    array_size = (width * height) // 8
    return bytes([0xFF] * array_size)


def create_black_image(width: int, height: int) -> bytes:
    """Create a black image (all bits set to 0)."""
    array_size = (width * height) // 8
    return bytes([0x00] * array_size)


def image_to_raw_data(img: Image.Image) -> bytes:
    """Convert PIL Image to raw 1-bit packed data."""
    # Convert to 1-bit
    img_1bit = img.convert("1", dither=Image.FLOYDSTEINBERG)

    # Get dimensions
    width, height = img_1bit.size
    array_size = (width * height) // 8

    # Pack bits into bytes (MSB first)
    raw_data = bytearray(array_size)
    pixels = list(img_1bit.getdata())

    for i, pixel in enumerate(pixels):
        byte_idx = i // 8
        bit_pos = 7 - (i % 8)  # MSB first
        if pixel:  # White pixel
            raw_data[byte_idx] |= 1 << bit_pos

    return bytes(raw_data)


def hexdump(data: bytes, max_bytes: int = 64):
    """Print hex dump of data for debugging."""
    print(f"Hex dump (first {min(max_bytes, len(data))} bytes):")

    for i in range(min(max_bytes, len(data))):
        if i % 16 == 0:
            print(f"\n{i:04x}: ", end="")
        print(f"{data[i]:02x} ", end="")
    print("\n")

    # Also show as binary for first 32 bytes to see bit patterns
    print("Binary representation (first 32 bytes):")
    for i in range(min(32, len(data))):
        if i % 4 == 0:
            print(f"\n{i:04x}: ", end="")
        print(f"{data[i]:08b} ", end="")
    print("\n")


def save_temp_image(img: Image.Image, prefix: str = "test") -> str:
    """Save image to temporary file for display."""
    import tempfile

    temp_file = tempfile.NamedTemporaryFile(suffix=".png", prefix=f"{prefix}_", delete=False)
    img.save(temp_file.name, "PNG")
    temp_file.close()
    return temp_file.name


def main():
    """Main test function."""
    print("=== E-ink Display Test ===")

    # Initialize configuration system
    print("1. Initializing configuration...")
    try:
        initialize_display_config()
        print("✓ Configuration initialized")
    except Exception as e:
        print(f"Warning: Config initialization failed: {e}")
        print("Using default configuration")

    # Get current firmware
    try:
        firmware = get_default_firmware()
        print(f"Current firmware: {firmware}")
    except Exception as e:
        print(f"Error getting firmware: {e}")

    # Check for environment variable override
    firmware_env = os.environ.get("DISTILLER_EINK_FIRMWARE")
    if firmware_env:
        print(f"Setting firmware from environment: {firmware_env}")
        try:
            if firmware_env == "EPD128x250":
                set_default_firmware(FirmwareType.EPD128x250)
            elif firmware_env == "EPD240x416":
                set_default_firmware(FirmwareType.EPD240x416)
            else:
                print(f"Unknown firmware type: {firmware_env}")

            firmware = get_default_firmware()
            print(f"Updated firmware: {firmware}")
        except Exception as e:
            print(f"Error setting firmware: {e}")

    # Get display dimensions
    print("\n2. Getting display dimensions...")
    try:
        display_info = get_display_info()
        width = display_info["width"]
        height = display_info["height"]
        array_size = display_info["data_size"]
        print(f"Display dimensions: {width}x{height} pixels")
        print(f"Required data size: {array_size} bytes")
    except Exception as e:
        print(f"Error getting display info: {e}")
        print("Attempting to determine dimensions from firmware configuration...")

        # Try to get dimensions based on firmware setting
        firmware_env = os.environ.get("DISTILLER_EINK_FIRMWARE", "EPD128x250")
        if firmware_env == "EPD240x416":
            width, height = 240, 416
        else:
            width, height = 128, 250
        array_size = (width * height) // 8
        print(f"Using {firmware_env} dimensions: {width}x{height} pixels")
        print(f"Required data size: {array_size} bytes")

    # Test image creation
    print("\n3. Testing image creation...")
    white_image = create_white_image(width, height)
    black_image = create_black_image(width, height)

    print(f"White image size: {len(white_image)} bytes")
    print(f"Black image size: {len(black_image)} bytes")

    if len(white_image) != array_size:
        print("ERROR: Image size mismatch!")
        print(f"Expected: {array_size} bytes, got: {len(white_image)} bytes")
        return 1

    # Test display initialization
    print("\n4. Testing display initialization...")
    try:
        display = Display(auto_init=True)
        print("✓ Display initialized successfully")
    except Exception as e:
        print(f"✗ Display initialization failed: {e}")
        print("This could be due to:")
        print("  - Hardware not connected")
        print("  - Insufficient permissions (try with sudo)")
        print("  - SPI/GPIO devices not available")
        print("  - Wrong firmware configuration")
        return 1

    try:
        # Get actual dimensions from display
        actual_width, actual_height = display.get_dimensions()
        print(f"Using display spec: {actual_width}x{actual_height}")

        # Update dimensions if they differ
        if actual_width != width or actual_height != height:
            width = actual_width
            height = actual_height
            array_size = (width * height) // 8
            print(f"Updated dimensions: {width}x{height}, data size: {array_size} bytes")
            # Recreate test images with correct size
            white_image = create_white_image(width, height)
            black_image = create_black_image(width, height)

        # Test display operations
        print("\n5. Testing display operations with patterns...")

        # Test 1: White image
        print("\n--- Test 1: White image ---")
        print("Displaying white image...")
        print("Expected: All bytes should be 0xFF")
        hexdump(white_image, 64)
        try:
            display.display_image(white_image, DisplayMode.FULL)
            print("✓ White image displayed")
        except Exception as e:
            print(f"Error displaying white image: {e}")
        time.sleep(2)

        # Test 2: Black image
        print("\n--- Test 2: Black image ---")
        print("Displaying black image...")
        print("Expected: All bytes should be 0x00")
        hexdump(black_image, 64)
        try:
            display.display_image(black_image, DisplayMode.FULL)
            print("✓ Black image displayed")
        except Exception as e:
            print(f"Error displaying black image: {e}")
        time.sleep(2)

        # Test 3: Checkerboard pattern
        print("\n--- Test 3: Checkerboard pattern ---")
        checkerboard = create_checkerboard_pattern(width, height, 16)
        checkerboard_data = image_to_raw_data(checkerboard)
        print(f"Checkerboard data size: {len(checkerboard_data)} bytes")
        print("Dithering method: Floyd-Steinberg")
        hexdump(checkerboard_data, 128)

        print("Displaying checkerboard pattern...")
        try:
            display.display_image(checkerboard_data, DisplayMode.FULL)
            print("✓ Checkerboard displayed")
        except Exception as e:
            print(f"Error displaying checkerboard: {e}")
        time.sleep(3)

        # Test 4: Vertical stripes
        print("\n--- Test 4: Vertical stripes ---")
        vertical = create_vertical_stripes(width, height, 8)
        vertical_data = image_to_raw_data(vertical)
        print(f"Vertical stripes data size: {len(vertical_data)} bytes")
        hexdump(vertical_data, 128)

        print("Displaying vertical stripes...")
        try:
            display.display_image(vertical_data, DisplayMode.FULL)
            print("✓ Vertical stripes displayed")
        except Exception as e:
            print(f"Error displaying vertical stripes: {e}")
        time.sleep(3)

        # Test 5: Horizontal stripes
        print("\n--- Test 5: Horizontal stripes ---")
        horizontal = create_horizontal_stripes(width, height, 8)
        horizontal_data = image_to_raw_data(horizontal)
        print(f"Horizontal stripes data size: {len(horizontal_data)} bytes")
        hexdump(horizontal_data, 128)

        print("Displaying horizontal stripes...")
        try:
            display.display_image(horizontal_data, DisplayMode.FULL)
            print("✓ Horizontal stripes displayed")
        except Exception as e:
            print(f"Error displaying horizontal stripes: {e}")
        time.sleep(3)

        # Test 6: Gradient with Floyd-Steinberg dithering
        print("\n--- Test 6: Gradient with Floyd-Steinberg dithering ---")
        gradient = create_gradient_pattern(width, height)
        temp_path = save_temp_image(gradient, "gradient")
        print(f"Gradient data size: {array_size} bytes")
        print("Dithering method: Floyd-Steinberg")

        print("Displaying gradient with Floyd-Steinberg...")
        try:
            display.display_image_auto(
                temp_path,
                DisplayMode.FULL,
                scaling=ScalingMethod.STRETCH,
                dithering=DitheringMethod.FLOYD_STEINBERG,
            )
            print("✓ Gradient displayed")
        except Exception as e:
            print(f"Error displaying gradient: {e}")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        time.sleep(3)

        # Test 7: Gradient with Simple thresholding
        print("\n--- Test 7: Gradient with Simple thresholding ---")
        temp_path = save_temp_image(gradient, "gradient_simple")
        print(f"Gradient simple data size: {array_size} bytes")
        print("Dithering method: Simple")

        print("Displaying gradient with Simple thresholding...")
        try:
            display.display_image_auto(
                temp_path,
                DisplayMode.FULL,
                scaling=ScalingMethod.STRETCH,
                dithering=DitheringMethod.SIMPLE,
            )
            print("✓ Gradient simple displayed")
        except Exception as e:
            print(f"Error displaying gradient simple: {e}")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        time.sleep(3)

        # Test with a real image file if provided as argument
        if len(sys.argv) > 1:
            image_path = sys.argv[1]
            if os.path.exists(image_path):
                print(f"\n--- Test 8: Loading image from file: {image_path} ---")

                # Test with Floyd-Steinberg, rotated and flipped
                print("Processing options:")
                print("  Dithering: Floyd-Steinberg")
                print("  Scaling: Letterbox")
                print("  Rotate: True")
                print("  Flip: True")

                try:
                    print("Displaying image with Floyd-Steinberg...")
                    display.display_image_auto(
                        image_path,
                        DisplayMode.FULL,
                        scaling=ScalingMethod.LETTERBOX,
                        dithering=DitheringMethod.FLOYD_STEINBERG,
                        rotate=True,
                        flop=True,
                    )
                    print("✓ Image displayed with Floyd-Steinberg")
                    time.sleep(5)

                    # Also test with Simple dithering for comparison
                    print("\n--- Test 9: Same image with Simple (ordered) dithering ---")
                    print("Processing with Simple dithering...")
                    print("  Dithering: Simple")

                    display.display_image_auto(
                        image_path,
                        DisplayMode.FULL,
                        scaling=ScalingMethod.LETTERBOX,
                        dithering=DitheringMethod.SIMPLE,
                        rotate=True,
                        flop=True,
                    )
                    print("✓ Image displayed with Simple dithering")
                    time.sleep(5)

                except Exception as e:
                    print(f"Error processing image file: {e}")
            else:
                print(f"Image file not found: {image_path}")
        else:
            print("\nTip: You can provide an image file as argument to test:")
            print(f"  python {sys.argv[0]} /path/to/image.png")

        # Clear display
        print("\nClearing display...")
        try:
            display.clear()
            print("✓ Display cleared")
        except Exception as e:
            print(f"Error clearing display: {e}")

        # Sleep display
        print("Putting display to sleep...")
        try:
            display.sleep()
            print("✓ Display sleeping")
        except Exception as e:
            print(f"Error putting display to sleep: {e}")

        # Cleanup
        print("Cleaning up...")
        display.close()
        print("✓ Cleanup completed")

    except Exception as e:
        print(f"Error during test: {e}")
        if display:
            display.close()
        return 1

    print("\n=== Test completed successfully ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
