#!/usr/bin/env python3
"""
Display module for CM5 SDK.
Provides functionality for e-ink display control and image display.
"""

import os
import ctypes
from ctypes import c_bool, c_char_p, c_uint32, POINTER
from enum import IntEnum
from typing import Optional, Tuple, Union
import tempfile
from PIL import Image, ImageOps


class DisplayError(Exception):
    """Custom exception for Display-related errors."""
    pass


class DisplayMode(IntEnum):
    """Display refresh modes."""
    FULL = 0      # Full refresh - slow but high quality
    PARTIAL = 1   # Partial refresh - fast updates


class FirmwareType:
    """Supported e-ink display firmware types."""
    EPD128x250 = "EPD128x250"
    EPD240x416 = "EPD240x416"


class ScalingMethod(IntEnum):
    """Image scaling methods for auto-conversion."""
    LETTERBOX = 0     # Maintain aspect ratio, add black borders
    CROP_CENTER = 1   # Center crop to fill display
    STRETCH = 2       # Stretch to fill display (may distort)


class DitheringMethod(IntEnum):
    """Dithering methods for 1-bit conversion."""
    FLOYD_STEINBERG = 0  # High quality dithering
    SIMPLE = 1           # Fast threshold conversion


class Display:
    """
    Display class for interacting with the CM5 e-ink display system.
    
    This class provides functionality to:
    - Display PNG images on the e-ink screen
    - Display raw 1-bit image data
    - Clear the display
    - Control display refresh modes
    - Manage display power states
    """
    
    # Display constants (will be updated dynamically)
    WIDTH = 128  # Default, will be updated after initialization
    HEIGHT = 250  # Default, will be updated after initialization
    ARRAY_SIZE = (128 * 250) // 8  # Default, will be updated after initialization
    
    def __init__(self, library_path: Optional[str] = None, auto_init: bool = True):
        """
        Initialize the Display object.
        
        Args:
            library_path: Optional path to the shared library. If None, searches common locations.
            auto_init: Whether to automatically initialize the display hardware
        
        Raises:
            DisplayError: If library can't be loaded or display can't be initialized
        """
        self._lib = None
        self._initialized = False
        
        # Find and load the shared library
        if library_path is None:
            library_path = self._find_library()
        
        if not os.path.exists(library_path):
            raise DisplayError(f"Display library not found: {library_path}")
        
        try:
            self._lib = ctypes.CDLL(library_path)
        except OSError as e:
            raise DisplayError(f"Failed to load display library: {e}")
        
        # Set up function signatures
        self._setup_function_signatures()
        
        if auto_init:
            self.initialize()
    
    def _find_library(self) -> str:
        """Find the shared library in common locations."""
        # Get the directory of this Python file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Common search paths
        search_paths = [
            # Debian package location
            "/opt/distiller-cm5-sdk/lib/libdistiller_display_sdk_shared.so",
            # Relative to this module
            os.path.join(current_dir, "lib", "libdistiller_display_sdk_shared.so"),
            # Build directory
            os.path.join(current_dir, "build", "libdistiller_display_sdk_shared.so"),
            # System locations
            "/usr/local/lib/libdistiller_display_sdk_shared.so",
            "/usr/lib/libdistiller_display_sdk_shared.so",
        ]
        
        for path in search_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                return abs_path
        
        raise DisplayError(
            f"Could not find libdistiller_display_sdk_shared.so in any of these locations:\n" +
            "\n".join(f"  - {path}" for path in search_paths)
        )
    
    def _setup_function_signatures(self):
        """Set up ctypes function signatures for all C functions."""
        
        # display_init() -> bool
        self._lib.display_init.restype = c_bool
        self._lib.display_init.argtypes = []
        
        # display_image_raw(const uint8_t* data, display_mode_t mode) -> bool
        self._lib.display_image_raw.restype = c_bool
        self._lib.display_image_raw.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int]
        
        # display_image_png(const char* filename, display_mode_t mode) -> bool
        self._lib.display_image_png.restype = c_bool
        self._lib.display_image_png.argtypes = [c_char_p, ctypes.c_int]
        
        # display_clear() -> bool
        self._lib.display_clear.restype = c_bool
        self._lib.display_clear.argtypes = []
        
        # display_sleep() -> void
        self._lib.display_sleep.restype = None
        self._lib.display_sleep.argtypes = []
        
        # display_cleanup() -> void
        self._lib.display_cleanup.restype = None
        self._lib.display_cleanup.argtypes = []
        
        # display_get_dimensions(uint32_t* width, uint32_t* height) -> void
        self._lib.display_get_dimensions.restype = None
        self._lib.display_get_dimensions.argtypes = [POINTER(c_uint32), POINTER(c_uint32)]
        
        # convert_png_to_1bit(const char* filename, uint8_t* output_data) -> bool
        self._lib.convert_png_to_1bit.restype = c_bool
        self._lib.convert_png_to_1bit.argtypes = [c_char_p, ctypes.POINTER(ctypes.c_ubyte)]
        
        # Configuration functions (optional - may not exist in older libraries)
        try:
            # display_set_firmware(const char* firmware_str) -> bool
            self._lib.display_set_firmware.restype = c_bool
            self._lib.display_set_firmware.argtypes = [c_char_p]
            
            # display_get_firmware(char* firmware_str, uint32_t max_len) -> bool
            self._lib.display_get_firmware.restype = c_bool
            self._lib.display_get_firmware.argtypes = [ctypes.c_char_p, c_uint32]
            
            # display_initialize_config() -> bool
            self._lib.display_initialize_config.restype = c_bool
            self._lib.display_initialize_config.argtypes = []
            
            self._config_available = True
        except AttributeError:
            # Configuration functions not available in this library version
            self._config_available = False
    
    def initialize(self) -> None:
        """
        Initialize the display hardware.
        
        Raises:
            DisplayError: If initialization fails
        """
        if self._initialized:
            return
        
        # Initialize configuration system first (if available)
        if hasattr(self, '_config_available') and self._config_available:
            try:
                config_success = self._lib.display_initialize_config()
                if not config_success:
                    # Config initialization failed, but continue with defaults
                    print("Warning: Failed to initialize config system, using defaults")
            except Exception as e:
                print(f"Warning: Config system error: {e}")
        
        success = self._lib.display_init()
        if not success:
            raise DisplayError("Failed to initialize display hardware")
        
        # Update dimensions based on current firmware
        self._update_dimensions()
        
        self._initialized = True
    
    def _update_dimensions(self) -> None:
        """Update display dimensions from the library."""
        try:
            width_ptr = ctypes.pointer(c_uint32())
            height_ptr = ctypes.pointer(c_uint32())
            self._lib.display_get_dimensions(width_ptr, height_ptr)
            
            self.WIDTH = width_ptr.contents.value
            self.HEIGHT = height_ptr.contents.value
            self.ARRAY_SIZE = (self.WIDTH * self.HEIGHT) // 8
            
            # Also update class-level constants for backwards compatibility
            Display.WIDTH = self.WIDTH
            Display.HEIGHT = self.HEIGHT
            Display.ARRAY_SIZE = self.ARRAY_SIZE
            
        except Exception as e:
            print(f"Warning: Could not get dimensions from library: {e}")
            # Keep default values
    
    def get_dimensions(self) -> Tuple[int, int]:
        """
        Get display dimensions.
        
        Returns:
            Tuple of (width, height) in pixels
        """
        if not self._initialized:
            # Try to get dimensions without initializing
            try:
                width_ptr = ctypes.pointer(c_uint32())
                height_ptr = ctypes.pointer(c_uint32())
                self._lib.display_get_dimensions(width_ptr, height_ptr)
                return (width_ptr.contents.value, height_ptr.contents.value)
            except:
                return (self.WIDTH, self.HEIGHT)
        return (self.WIDTH, self.HEIGHT)
    
    def display_image(self, image: Union[str, bytes], mode: DisplayMode = DisplayMode.FULL, rotate: Union[bool, int] = False, flip_horizontal: bool = False, invert_colors: bool = False, src_width: int = None, src_height: int = None) -> None:
        """
        Display an image on the e-ink screen.
        
        Args:
            image: Either a PNG file path (string) or raw 1-bit image data (bytes)
            mode: Display refresh mode
            rotate: Rotation angle in degrees (0, 90, 180, 270) or bool for backward compatibility
                   If True, rotate 90 degrees CCW (landscape 250x128 to portrait 128x250)
                   If False or 0, no rotation
            flip_horizontal: If True, mirror the image horizontally (left-right)
            invert_colors: If True, invert colors (black↔white)
            src_width: Source width in pixels (required when transforming raw data)
            src_height: Source height in pixels (required when transforming raw data)
            
        Raises:
            DisplayError: If display operation fails
        """
        if not self._initialized:
            raise DisplayError("Display not initialized. Call initialize() first.")
        
        # Handle backward compatibility for boolean rotate parameter
        if isinstance(rotate, bool):
            rotation_degrees = 90 if rotate else 0
        else:
            rotation_degrees = rotate
        
        if isinstance(image, str):
            # PNG file path
            self._display_png(image, mode, rotation_degrees, flip_horizontal, invert_colors)
        elif isinstance(image, (bytes, bytearray)):
            # Raw image data
            raw_data = bytes(image)
            
            if flip_horizontal or rotation_degrees != 0 or invert_colors:
                if src_width is None or src_height is None:
                    raise DisplayError("src_width and src_height are required when transforming raw data")
                
                # Apply transformations in DistillerGUI order: flip, rotate, then invert colors
                if flip_horizontal:
                    raw_data = flip_bitpacked_horizontal(raw_data, src_width, src_height)
                
                if rotation_degrees != 0:
                    # Use the generic rotation function
                    raw_data = rotate_bitpacked(raw_data, src_width, src_height, rotation_degrees)
                
                if invert_colors:
                    raw_data = invert_bitpacked_colors(raw_data)
            
            self._display_raw(raw_data, mode)
        else:
            raise DisplayError(f"Invalid image type: {type(image)}. Expected str or bytes.")
    
    def _display_png(self, filename: str, mode: DisplayMode, rotate: Union[bool, int] = False, flip_horizontal: bool = False, invert_colors: bool = False) -> None:
        """Display a PNG image file."""
        if not os.path.exists(filename):
            raise DisplayError(f"PNG file not found: {filename}")
        
        # Handle backward compatibility for boolean rotate parameter
        if isinstance(rotate, bool):
            rotation_degrees = 90 if rotate else 0
        else:
            rotation_degrees = rotate
        
        if rotation_degrees != 0 or flip_horizontal or invert_colors:
            # For PNG transformations, convert to raw data first
            raw_data = self.convert_png_to_raw(filename)
            # Assume PNG is 250x128 landscape format when transforming
            
            # Apply transformations in DistillerGUI order: flip, rotate, then invert colors
            if flip_horizontal:
                raw_data = flip_bitpacked_horizontal(raw_data, 250, 128)
                
            if rotation_degrees != 0:
                # Use the generic rotation function
                raw_data = rotate_bitpacked(raw_data, 250, 128, rotation_degrees)
                
            if invert_colors:
                raw_data = invert_bitpacked_colors(raw_data)
                
            self._display_raw(raw_data, mode)
        else:
            # Direct PNG display (must be 128x250)
            filename_bytes = filename.encode('utf-8')
            success = self._lib.display_image_png(filename_bytes, int(mode))
            if not success:
                raise DisplayError(f"Failed to display PNG image: {filename}")
    
    def _display_raw(self, data: bytes, mode: DisplayMode) -> None:
        """Display raw 1-bit image data."""
        if len(data) != self.ARRAY_SIZE:
            raise DisplayError(f"Data must be exactly {self.ARRAY_SIZE} bytes, got {len(data)}")
        
        # Convert bytes to ctypes array
        data_array = (ctypes.c_ubyte * len(data))(*data)
        
        success = self._lib.display_image_raw(data_array, int(mode))
        if not success:
            raise DisplayError("Failed to display raw image data")
    
    def clear(self) -> None:
        """
        Clear the display (set to white).
        
        Raises:
            DisplayError: If clear operation fails
        """
        if not self._initialized:
            raise DisplayError("Display not initialized. Call initialize() first.")
        
        success = self._lib.display_clear()
        if not success:
            raise DisplayError("Failed to clear display")
    
    def sleep(self) -> None:
        """Put display to sleep for power saving."""
        if self._initialized:
            self._lib.display_sleep()
    
    def get_dimensions(self) -> Tuple[int, int]:
        """
        Get display dimensions.
        
        Returns:
            Tuple of (width, height) in pixels
        """
        width = c_uint32()
        height = c_uint32()
        self._lib.display_get_dimensions(ctypes.byref(width), ctypes.byref(height))
        return (width.value, height.value)
    
    def convert_png_to_raw(self, filename: str) -> bytes:
        """
        Convert PNG file to raw 1-bit data.
        
        Args:
            filename: Path to PNG file (must be exactly 128x250 pixels)
            
        Returns:
            Raw 1-bit packed image data (4000 bytes)
            
        Raises:
            DisplayError: If conversion fails
        """
        if not os.path.exists(filename):
            raise DisplayError(f"PNG file not found: {filename}")
        
        # Create output buffer
        output_data = (ctypes.c_ubyte * self.ARRAY_SIZE)()
        filename_bytes = filename.encode('utf-8')
        
        success = self._lib.convert_png_to_1bit(filename_bytes, output_data)
        if not success:
            raise DisplayError(f"Failed to convert PNG: {filename}")
        
        # Convert ctypes array to bytes
        return bytes(output_data)
    
    def is_initialized(self) -> bool:
        """Check if display is initialized."""
        return self._initialized
    
    def close(self) -> None:
        """Cleanup display resources."""
        if self._initialized:
            self._lib.display_cleanup()
            self._initialized = False
    
    def set_firmware(self, firmware_type: str) -> None:
        """
        Set the default firmware type for the display.
        
        Args:
            firmware_type: Firmware type string (e.g., "EPD128x250", "EPD240x416")
            
        Raises:
            DisplayError: If firmware type is invalid or setting fails
        """
        if not (hasattr(self, '_config_available') and self._config_available):
            raise DisplayError("Configuration system not available. Please rebuild the Rust library.")
        
        firmware_bytes = firmware_type.encode('utf-8')
        success = self._lib.display_set_firmware(firmware_bytes)
        if not success:
            raise DisplayError(f"Failed to set firmware type: {firmware_type}")
    
    def get_firmware(self) -> str:
        """
        Get the current default firmware type.
        
        Returns:
            Current firmware type string
            
        Raises:
            DisplayError: If getting firmware fails
        """
        if not (hasattr(self, '_config_available') and self._config_available):
            raise DisplayError("Configuration system not available. Please rebuild the Rust library.")
        
        buffer = ctypes.create_string_buffer(64)  # Should be enough for firmware names
        success = self._lib.display_get_firmware(buffer, 64)
        if not success:
            raise DisplayError("Failed to get current firmware type")
        return buffer.value.decode('utf-8')
    
    def initialize_config(self) -> None:
        """
        Initialize the configuration system.
        This loads configuration from environment variables and config files.
        
        Raises:
            DisplayError: If configuration initialization fails
        """
        if not (hasattr(self, '_config_available') and self._config_available):
            raise DisplayError("Configuration system not available. Please rebuild the Rust library.")
        
        success = self._lib.display_initialize_config()
        if not success:
            raise DisplayError("Failed to initialize configuration system")
    
    def __enter__(self):
        """Context manager entry."""
        if not self._initialized:
            self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def _get_display_dimensions(self) -> Tuple[int, int]:
        """Get current display dimensions."""
        if not self._initialized:
            self.initialize()
        return self.WIDTH, self.HEIGHT
    
    def _convert_png_auto(self, image_path: str, scaling: ScalingMethod = ScalingMethod.LETTERBOX, 
                         dithering: DitheringMethod = DitheringMethod.FLOYD_STEINBERG,
                         rotate: Union[bool, int] = False, flop: bool = False,
                         crop_x: Optional[int] = None, crop_y: Optional[int] = None) -> str:
        """
        Convert any PNG to display-compatible format.
        
        Args:
            image_path: Path to source PNG file
            scaling: How to scale the image to fit display
            dithering: Dithering method for 1-bit conversion
            rotate: Rotation angle in degrees (0, 90, 180, 270) or bool for backward compatibility
                   If True, rotate 90 degrees counter-clockwise
                   If False or 0, no rotation
            flop: If True, flip image horizontally (left-right mirror)
            crop_x: X position for crop when using CROP_CENTER (None = center)
            crop_y: Y position for crop when using CROP_CENTER (None = center)
            
        Returns:
            Path to converted temporary PNG file
            
        Raises:
            DisplayError: If conversion fails
        """
        if not os.path.exists(image_path):
            raise DisplayError(f"PNG file not found: {image_path}")
        
        # Get display dimensions
        display_width, display_height = self._get_display_dimensions()
        
        try:
            # Load and process the image
            with Image.open(image_path) as img:
                # Convert to RGB if needed (handles RGBA, palette, etc.)
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                # Apply transformations (rotate, flop)
                if flop:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                
                # Handle rotation with degree support
                if rotate:
                    # Convert boolean to degrees for backward compatibility
                    if isinstance(rotate, bool):
                        rotation_degrees = 90 if rotate else 0
                    else:
                        rotation_degrees = rotate % 360
                    
                    # Apply rotation based on degrees
                    if rotation_degrees == 90:
                        img = img.transpose(Image.ROTATE_90)
                    elif rotation_degrees == 180:
                        img = img.transpose(Image.ROTATE_180)
                    elif rotation_degrees == 270:
                        img = img.transpose(Image.ROTATE_270)
                    # 0 degrees or other values: no rotation
                
                # Scale the image based on method
                processed_img = self._scale_image(img, display_width, display_height, scaling, crop_x, crop_y)
                
                # Convert to 1-bit with dithering
                if dithering == DitheringMethod.FLOYD_STEINBERG:
                    bw_img = processed_img.convert('1', dither=Image.FLOYDSTEINBERG)
                else:
                    bw_img = processed_img.convert('1', dither=Image.NONE)
                
                # Save to temporary file
                temp_fd, temp_path = tempfile.mkstemp(suffix='.png', prefix='eink_auto_')
                try:
                    os.close(temp_fd)
                    bw_img.save(temp_path, 'PNG')
                    return temp_path
                except Exception as e:
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                    raise DisplayError(f"Failed to save converted image: {e}")
                
        except Exception as e:
            raise DisplayError(f"Failed to convert PNG: {e}")
    
    def _scale_image(self, img: Image.Image, target_width: int, target_height: int, 
                    scaling: ScalingMethod, crop_x: Optional[int] = None, 
                    crop_y: Optional[int] = None) -> Image.Image:
        """
        Scale image according to specified method.
        
        Args:
            img: Source PIL Image
            target_width: Target display width
            target_height: Target display height
            scaling: Scaling method to use
            crop_x: X position for crop when using CROP_CENTER (None = center)
            crop_y: Y position for crop when using CROP_CENTER (None = center)
            
        Returns:
            Scaled PIL Image
        """
        orig_width, orig_height = img.size
        
        if scaling == ScalingMethod.STRETCH:
            # Simple stretch to fill display
            return img.resize((target_width, target_height), Image.LANCZOS)
        
        elif scaling == ScalingMethod.CROP_CENTER:
            # Scale to fill display completely, then crop with auto positioning
            scale_w = target_width / orig_width
            scale_h = target_height / orig_height
            scale = max(scale_w, scale_h)  # Scale to fill
            
            new_width = int(orig_width * scale)
            new_height = int(orig_height * scale)
            
            # Resize first
            scaled_img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Calculate crop position with auto centering
            if crop_x is None:
                left = (new_width - target_width) // 2  # Auto center horizontally
            else:
                left = max(0, min(crop_x, new_width - target_width))  # Clamp to valid range
            
            if crop_y is None:
                top = (new_height - target_height) // 2  # Auto center vertically
            else:
                top = max(0, min(crop_y, new_height - target_height))  # Clamp to valid range
            
            right = left + target_width
            bottom = top + target_height
            
            return scaled_img.crop((left, top, right, bottom))
        
        else:  # LETTERBOX (default)
            # Scale to fit within display, maintaining aspect ratio
            scale_w = target_width / orig_width
            scale_h = target_height / orig_height
            scale = min(scale_w, scale_h)  # Scale to fit
            
            new_width = int(orig_width * scale)
            new_height = int(orig_height * scale)
            
            # Resize the image
            scaled_img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Create new image with target dimensions and paste scaled image centered
            result = Image.new('RGB', (target_width, target_height), 'white')
            paste_x = (target_width - new_width) // 2
            paste_y = (target_height - new_height) // 2
            result.paste(scaled_img, (paste_x, paste_y))
            
            return result
    
    def display_png_auto(self, image_path: str, mode: DisplayMode = DisplayMode.FULL,
                        scaling: ScalingMethod = ScalingMethod.LETTERBOX,
                        dithering: DitheringMethod = DitheringMethod.FLOYD_STEINBERG,
                        rotate: Union[bool, int] = False, flop: bool = False,
                        crop_x: Optional[int] = None, crop_y: Optional[int] = None,
                        cleanup_temp: bool = True) -> bool:
        """
        Display any PNG image with automatic conversion to display specifications.
        
        Args:
            image_path: Path to source PNG file
            mode: Display refresh mode
            scaling: How to scale the image to fit display
            dithering: Dithering method for 1-bit conversion
            rotate: Rotation angle in degrees (0, 90, 180, 270) or bool for backward compatibility
                   If True, rotate 90 degrees counter-clockwise
                   If False or 0, no rotation
            flop: If True, flip image horizontally (left-right mirror)
            crop_x: X position for crop when using CROP_CENTER (None = center)
            crop_y: Y position for crop when using CROP_CENTER (None = center)
            cleanup_temp: Whether to cleanup temporary files
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            DisplayError: If display operation fails
        """
        temp_path = None
        try:
            # Convert image to display format
            temp_path = self._convert_png_auto(image_path, scaling, dithering, rotate, flop, crop_x, crop_y)
            
            # Display the converted image
            self.display_image(temp_path, mode, rotate=False)
            return True
            
        except Exception as e:
            raise DisplayError(f"Failed to auto-display PNG: {e}")
            
        finally:
            # Cleanup temporary file
            if cleanup_temp and temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass  # Ignore cleanup errors


# Convenience functions for simple usage (following SDK pattern)
def display_png(filename: str, mode: DisplayMode = DisplayMode.FULL, rotate: Union[bool, int] = False, 
                auto_convert: bool = False, scaling: ScalingMethod = ScalingMethod.LETTERBOX,
                dithering: DitheringMethod = DitheringMethod.FLOYD_STEINBERG,
                flop: bool = False, crop_x: Optional[int] = None, crop_y: Optional[int] = None) -> None:
    """
    Convenience function to display a PNG image.
    
    Args:
        filename: Path to PNG file 
        mode: Display refresh mode
        rotate: Rotation angle in degrees (0, 90, 180, 270) or bool for backward compatibility
               If True, rotate 90 degrees CCW (landscape 250x128 to portrait 128x250)
               If False or 0, no rotation
        auto_convert: If True, automatically convert any PNG to display format
        scaling: How to scale the image to fit display (only used with auto_convert)
        dithering: Dithering method for 1-bit conversion (only used with auto_convert)
        flop: If True, flip image horizontally (only used with auto_convert)
        crop_x: X position for crop when using CROP_CENTER with auto_convert (None = center)
        crop_y: Y position for crop when using CROP_CENTER with auto_convert (None = center)
    """
    with Display() as display:
        if auto_convert:
            display.display_png_auto(filename, mode, scaling, dithering, rotate, flop, crop_x, crop_y)
        else:
            display.display_image(filename, mode, rotate)


def display_png_auto(filename: str, mode: DisplayMode = DisplayMode.FULL,
                    scaling: ScalingMethod = ScalingMethod.LETTERBOX,
                    dithering: DitheringMethod = DitheringMethod.FLOYD_STEINBERG,
                    rotate: Union[bool, int] = False, flop: bool = False,
                    crop_x: Optional[int] = None, crop_y: Optional[int] = None) -> None:
    """
    Convenience function to display any PNG image with automatic conversion.
    
    Args:
        filename: Path to PNG file (any size, any format)
        mode: Display refresh mode
        scaling: How to scale the image to fit display
        dithering: Dithering method for 1-bit conversion
        rotate: Rotation angle in degrees (0, 90, 180, 270) or bool for backward compatibility
               If True, rotate 90 degrees counter-clockwise
               If False or 0, no rotation
        flop: If True, flip image horizontally (left-right mirror)
        crop_x: X position for crop when using CROP_CENTER (None = center)
        crop_y: Y position for crop when using CROP_CENTER (None = center)
    """
    with Display() as display:
        display.display_png_auto(filename, mode, scaling, dithering, rotate, flop, crop_x, crop_y)


def clear_display() -> None:
    """Convenience function to clear the display."""
    with Display() as display:
        display.clear()


def get_display_info() -> dict:
    """
    Get display information.
    
    Returns:
        Dictionary with display specs
    """
    return {
        "width": Display.WIDTH,
        "height": Display.HEIGHT,
        "data_size": Display.ARRAY_SIZE,
        "format": "1-bit monochrome",
        "type": "e-ink"
    }


def rotate_bitpacked_ccw_90(src_data: bytes, src_width: int, src_height: int) -> bytes:
    """
    Rotate 1-bit packed bitmap data 90 degrees counter-clockwise.
    
    This function converts landscape data (e.g., 250x128) to portrait data (e.g., 128x250)
    for display on portrait-oriented e-ink screens.
    
    Args:
        src_data: Source 1-bit packed image data
        src_width: Source image width in pixels  
        src_height: Source image height in pixels
        
    Returns:
        Rotated 1-bit packed data with dimensions (src_height x src_width)
        
    Raises:
        ValueError: If data size doesn't match expected size
    """
    # Validate input data size
    expected_bytes = (src_width * src_height + 7) // 8
    if len(src_data) < expected_bytes:
        raise ValueError(f"Input data too small. Expected {expected_bytes} bytes, got {len(src_data)}")
    
    # Calculate destination dimensions and buffer size
    dst_width = src_height
    dst_height = src_width  
    dst_bytes = (dst_width * dst_height + 7) // 8
    
    # Initialize destination buffer (all zeros = white)
    dst_data = bytearray(dst_bytes)
    
    # For each pixel in source
    for src_y in range(src_height):
        for src_x in range(src_width):
            # Get bit from source - MSB first
            src_bit_idx = src_y * src_width + src_x
            src_byte_idx = src_bit_idx // 8
            src_bit_pos = 7 - (src_bit_idx % 8)  # MSB first
            src_bit = (src_data[src_byte_idx] >> src_bit_pos) & 1
            
            # Calculate destination coordinates (counter-clockwise rotation)
            dst_x = src_y
            dst_y = src_width - 1 - src_x
            
            # Set bit in destination - MSB first
            dst_bit_idx = dst_y * dst_width + dst_x  
            dst_byte_idx = dst_bit_idx // 8
            dst_bit_pos = 7 - (dst_bit_idx % 8)  # MSB first
            
            if src_bit:
                dst_data[dst_byte_idx] |= (1 << dst_bit_pos)
    
    return bytes(dst_data)


def rotate_bitpacked_cw_90(src_data: bytes, src_width: int, src_height: int) -> bytes:
    """
    Rotate 1-bit packed bitmap data 90 degrees clockwise.
    
    This function rotates the image 90 degrees clockwise (equivalent to 270 degrees
    counter-clockwise). It swaps width and height dimensions.
    
    Args:
        src_data: Source 1-bit packed image data
        src_width: Source image width in pixels
        src_height: Source image height in pixels
        
    Returns:
        Rotated 1-bit packed data with dimensions (src_height x src_width)
        
    Raises:
        ValueError: If data size doesn't match expected size
    """
    # Validate input data size
    expected_bytes = (src_width * src_height + 7) // 8
    if len(src_data) < expected_bytes:
        raise ValueError(f"Input data too small. Expected {expected_bytes} bytes, got {len(src_data)}")
    
    # Calculate destination dimensions and buffer size
    dst_width = src_height
    dst_height = src_width
    dst_bytes = (dst_width * dst_height + 7) // 8
    
    # Initialize destination buffer (all zeros = white)
    dst_data = bytearray(dst_bytes)
    
    # For each pixel in source
    for src_y in range(src_height):
        for src_x in range(src_width):
            # Get bit from source - MSB first
            src_bit_idx = src_y * src_width + src_x
            src_byte_idx = src_bit_idx // 8
            src_bit_pos = 7 - (src_bit_idx % 8)  # MSB first
            src_bit = (src_data[src_byte_idx] >> src_bit_pos) & 1
            
            # Calculate destination coordinates (clockwise rotation)
            dst_x = src_height - 1 - src_y
            dst_y = src_x
            
            # Set bit in destination - MSB first
            dst_bit_idx = dst_y * dst_width + dst_x
            dst_byte_idx = dst_bit_idx // 8
            dst_bit_pos = 7 - (dst_bit_idx % 8)  # MSB first
            
            if src_bit:
                dst_data[dst_byte_idx] |= (1 << dst_bit_pos)
    
    return bytes(dst_data)


def rotate_bitpacked_180(src_data: bytes, src_width: int, src_height: int) -> bytes:
    """
    Rotate 1-bit packed bitmap data 180 degrees.
    
    This function rotates the image 180 degrees, keeping the same dimensions
    but reversing both horizontal and vertical orientations.
    
    Args:
        src_data: Source 1-bit packed image data
        src_width: Source image width in pixels
        src_height: Source image height in pixels
        
    Returns:
        Rotated 1-bit packed data with same dimensions
        
    Raises:
        ValueError: If data size doesn't match expected size
    """
    # Validate input data size
    expected_bytes = (src_width * src_height + 7) // 8
    if len(src_data) < expected_bytes:
        raise ValueError(f"Input data too small. Expected {expected_bytes} bytes, got {len(src_data)}")
    
    # Initialize destination buffer (same size as source)
    dst_data = bytearray(expected_bytes)
    
    # For each pixel in source
    for src_y in range(src_height):
        for src_x in range(src_width):
            # Get bit from source - MSB first
            src_bit_idx = src_y * src_width + src_x
            src_byte_idx = src_bit_idx // 8
            src_bit_pos = 7 - (src_bit_idx % 8)  # MSB first
            src_bit = (src_data[src_byte_idx] >> src_bit_pos) & 1
            
            # Calculate destination coordinates (180 degree rotation)
            dst_x = src_width - 1 - src_x
            dst_y = src_height - 1 - src_y
            
            # Set bit in destination - MSB first
            dst_bit_idx = dst_y * src_width + dst_x
            dst_byte_idx = dst_bit_idx // 8
            dst_bit_pos = 7 - (dst_bit_idx % 8)  # MSB first
            
            if src_bit:
                dst_data[dst_byte_idx] |= (1 << dst_bit_pos)
    
    return bytes(dst_data)


def rotate_bitpacked(src_data: bytes, src_width: int, src_height: int, degrees: int) -> bytes:
    """
    Rotate 1-bit packed bitmap data by specified degrees.
    
    This is a generic rotation function that routes to specific implementations
    based on the rotation angle.
    
    Args:
        src_data: Source 1-bit packed image data
        src_width: Source image width in pixels
        src_height: Source image height in pixels
        degrees: Rotation angle in degrees (0, 90, 180, 270, or multiples)
        
    Returns:
        Rotated 1-bit packed data
        
    Raises:
        ValueError: If data size doesn't match expected size
    """
    # Normalize degrees to 0-359 range
    normalized_degrees = degrees % 360
    
    if normalized_degrees == 0:
        # No rotation needed
        return src_data
    elif normalized_degrees == 90:
        # 90 degrees counter-clockwise
        return rotate_bitpacked_ccw_90(src_data, src_width, src_height)
    elif normalized_degrees == 180:
        # 180 degrees
        return rotate_bitpacked_180(src_data, src_width, src_height)
    elif normalized_degrees == 270:
        # 270 degrees counter-clockwise (90 degrees clockwise)
        return rotate_bitpacked_cw_90(src_data, src_width, src_height)
    else:
        # For non-90-degree multiples, find the closest 90-degree multiple
        closest = round(normalized_degrees / 90) * 90
        if closest == 360:
            closest = 0
        return rotate_bitpacked(src_data, src_width, src_height, closest)


def flip_bitpacked_horizontal(src_data: bytes, src_width: int, src_height: int) -> bytes:
    """
    Flip 1-bit packed bitmap data horizontally (left-right mirror).
    
    This function mirrors the image horizontally, which is useful for correcting
    display orientation issues or mirrored content.
    
    Args:
        src_data: Source 1-bit packed image data
        src_width: Source image width in pixels  
        src_height: Source image height in pixels
        
    Returns:
        Horizontally flipped 1-bit packed data with same dimensions
        
    Raises:
        ValueError: If data size doesn't match expected size
    """
    # Validate input data size
    expected_bytes = (src_width * src_height + 7) // 8
    if len(src_data) < expected_bytes:
        raise ValueError(f"Input data too small. Expected {expected_bytes} bytes, got {len(src_data)}")
    
    # Initialize destination buffer (same size as source)
    dst_data = bytearray(expected_bytes)
    
    # Flip horizontally: for each row, reverse the column order
    for y in range(src_height):
        for x in range(src_width):
            # Get bit from source position
            src_bit_idx = y * src_width + x
            src_byte_idx = src_bit_idx // 8
            src_bit_pos = 7 - (src_bit_idx % 8)  # MSB first
            src_bit = (src_data[src_byte_idx] >> src_bit_pos) & 1
            
            # Calculate flipped x position (mirror horizontally)
            flipped_x = src_width - 1 - x
            
            # Set bit in flipped position
            dst_bit_idx = y * src_width + flipped_x
            dst_byte_idx = dst_bit_idx // 8
            dst_bit_pos = 7 - (dst_bit_idx % 8)  # MSB first
            
            if src_bit:
                dst_data[dst_byte_idx] |= (1 << dst_bit_pos)
    
    return bytes(dst_data)


def invert_bitpacked_colors(src_data: bytes) -> bytes:
    """
    Invert colors in 1-bit packed bitmap data (black↔white).
    
    This function flips all bits to invert the colors, which is needed
    for some e-ink displays that have inverted color interpretation.
    
    Args:
        src_data: Source 1-bit packed image data
        
    Returns:
        Color-inverted 1-bit packed data (same size as input)
    """
    # Invert all bits in the data (flip white<->black)
    return bytes(~byte & 0xFF for byte in src_data)


# Configuration convenience functions
def set_default_firmware(firmware_type: str) -> None:
    """
    Set the default firmware type globally.
    
    Args:
        firmware_type: Firmware type string (e.g., FirmwareType.EPD128x250, FirmwareType.EPD240x416)
        
    Raises:
        DisplayError: If firmware type is invalid or setting fails
        
    Example:
        set_default_firmware(FirmwareType.EPD240x416)
    """
    display = Display(auto_init=False)
    display.set_firmware(firmware_type)


def get_default_firmware() -> str:
    """
    Get the current default firmware type.
    
    Returns:
        Current firmware type string
        
    Raises:
        DisplayError: If getting firmware fails
        
    Example:
        current_fw = get_default_firmware()
        print(f"Current firmware: {current_fw}")
    """
    display = Display(auto_init=False)
    return display.get_firmware()


def initialize_display_config() -> None:
    """
    Initialize the display configuration system.
    
    This loads configuration from:
    - Environment variable: DISTILLER_EINK_FIRMWARE
    - Config files: /opt/distiller-cm5-sdk/eink.conf, ./eink.conf, ~/.distiller/eink.conf
    - Falls back to EPD128x250 default
    
    Raises:
        DisplayError: If configuration initialization fails
        
    Example:
        # Set via environment variable
        import os
        os.environ['DISTILLER_EINK_FIRMWARE'] = 'EPD240x416'
        initialize_display_config()
        
        # Or via config file
        # echo "firmware=EPD240x416" > /opt/distiller-cm5-sdk/eink.conf
        initialize_display_config()
    """
    display = Display(auto_init=False)
    display.initialize_config() 