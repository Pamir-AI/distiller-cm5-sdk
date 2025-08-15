#!/usr/bin/env python3
"""
Display module for CM5 SDK.
Provides functionality for e-ink display control and image display.
"""

import ctypes
import hashlib
import json
import os
import tempfile
import threading
import weakref
from ctypes import POINTER, c_bool, c_char_p, c_uint32
from enum import Enum, IntEnum
from typing import Any

from PIL import Image


class DisplayError(Exception):
    """Custom exception for Display-related errors."""
    pass


class DisplayMode(IntEnum):
    """Display refresh modes."""
    FULL = 0      # Full refresh - slow but high quality
    PARTIAL = 1   # Partial refresh - fast updates


class FirmwareType(Enum):
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


class ImageCacheManager:
    """
    Manages caching of converted images to avoid repeated processing.
    Uses LRU cache with JSON-based persistence for security.
    Thread-safe implementation.
    """

    # Class-level lock for thread safety
    _lock = threading.RLock()

    def __init__(self, max_size: int = 100, persist_path: str | None = None):
        """
        Initialize the image cache manager.

        Args:
            max_size: Maximum number of cached entries
            persist_path: Optional path to persist cache between sessions
        """
        self.max_size = max_size
        self.persist_path = persist_path
        self._cache: dict[str, dict[str, Any]] = {}
        self._temp_files: dict[str, str] = {}  # Track temp files for cleanup
        self._finalizer = None

        # Load persisted cache if available (JSON format for security)
        if persist_path and os.path.exists(persist_path):
            self._load_cache_from_json(persist_path)

        # Use weakref finalizer instead of atexit to avoid circular references
        self._finalizer = weakref.finalize(self, self._cleanup_static,
                                          list(self._temp_files.values()))

    def _load_cache_from_json(self, persist_path: str) -> None:
        """Load cache from JSON file with validation."""
        try:
            with open(persist_path) as f:
                saved_cache = json.load(f)

                # Validate cache structure and version
                if not isinstance(saved_cache, dict):
                    return

                cache_version = saved_cache.get('version', 0)
                if cache_version != 1:  # Current cache version
                    return

                entries = saved_cache.get('entries', {})
                for key, entry in entries.items():
                    # Validate entry structure
                    if not self._validate_cache_entry(entry):
                        continue

                    # Check if temp file still exists
                    if 'temp_path' in entry and os.path.exists(entry['temp_path']):
                        self._cache[key] = entry
                        self._temp_files[key] = entry['temp_path']
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Warning: Could not load cache from {persist_path}: {e}")

    def _validate_cache_entry(self, entry: Any) -> bool:
        """Validate cache entry structure for security."""
        if not isinstance(entry, dict):
            return False

        required_keys = ['temp_path', 'source_path', 'params']
        if not all(key in entry for key in required_keys):
            return False

        # Validate temp_path is within allowed directory
        temp_path = entry.get('temp_path', '')
        if not temp_path.startswith(tempfile.gettempdir()):
            return False

        return True

    @staticmethod
    def _cleanup_static(temp_files: list[str]) -> None:
        """Static cleanup method to avoid circular references."""
        for temp_path in temp_files:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except OSError:
                pass

    def _generate_cache_key(self, image_path: str, display_width: int, display_height: int,
                           scaling: int, dithering: int, rotate: bool, flop: bool,
                           crop_x: int | None, crop_y: int | None) -> str:
        """Generate a unique cache key for the conversion parameters."""
        # Get file modification time for cache invalidation
        try:
            if os.path.exists(image_path):
                mtime = os.path.getmtime(image_path)
            else:
                # For non-existent files, use a unique invalid marker
                mtime = -1
        except OSError:
            mtime = -1

        # Create a unique key from all parameters
        key_data = {
            'path': image_path,
            'mtime': mtime,
            'width': display_width,
            'height': display_height,
            'scaling': scaling,
            'dithering': dithering,
            'rotate': rotate,
            'flop': flop,
            'crop_x': crop_x,
            'crop_y': crop_y
        }

        # Generate hash of the key data
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def get(self, image_path: str, display_width: int, display_height: int,
            scaling: int, dithering: int, rotate: bool, flop: bool,
            crop_x: int | None, crop_y: int | None) -> str | None:
        """
        Get cached converted image path if available. Thread-safe.

        Returns:
            Path to cached temporary file, or None if not cached
        """
        with self._lock:
            key = self._generate_cache_key(image_path, display_width, display_height,
                                          scaling, dithering, rotate, flop, crop_x, crop_y)

            if key in self._cache:
                entry = self._cache[key]
                # Verify the temp file still exists
                if os.path.exists(entry['temp_path']):
                    # Move to end (most recently used)
                    self._cache.pop(key)
                    self._cache[key] = entry
                    return entry['temp_path']
                else:
                    # Clean up invalid entry
                    self._cache.pop(key, None)
                    self._temp_files.pop(key, None)

            return None

    def put(self, image_path: str, display_width: int, display_height: int,
            scaling: int, dithering: int, rotate: bool, flop: bool,
            crop_x: int | None, crop_y: int | None, temp_path: str) -> None:
        """
        Store converted image in cache. Thread-safe.

        Args:
            temp_path: Path to the converted temporary file
        """
        with self._lock:
            # Validate temp_path is in temp directory
            if not temp_path.startswith(tempfile.gettempdir()):
                raise ValueError(f"Invalid temp path: {temp_path}")

            key = self._generate_cache_key(image_path, display_width, display_height,
                                          scaling, dithering, rotate, flop, crop_x, crop_y)

            # Enforce max size (remove oldest entries)
            while len(self._cache) >= self.max_size:
                # Remove oldest (first) entry
                oldest_key = next(iter(self._cache))
                self._remove_entry(oldest_key)

            # Add new entry
            self._cache[key] = {
                'temp_path': temp_path,
                'source_path': image_path,
                'params': {
                    'width': display_width,
                    'height': display_height,
                    'scaling': scaling,
                    'dithering': dithering,
                    'rotate': rotate,
                    'flop': flop,
                    'crop_x': crop_x,
                    'crop_y': crop_y
                }
            }
            self._temp_files[key] = temp_path

            # Update finalizer with new temp files list
            if self._finalizer:
                self._finalizer.detach()
            self._finalizer = weakref.finalize(self, self._cleanup_static,
                                              list(self._temp_files.values()))

            # Persist cache if configured
            self._persist()

    def _remove_entry(self, key: str) -> None:
        """Remove a cache entry and clean up its temp file."""
        self._cache.pop(key, None)
        temp_path = self._temp_files.pop(key, None)

        # Clean up temp file if it exists and is not used elsewhere
        if temp_path and temp_path not in self._temp_files.values():
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    def clear(self) -> None:
        """Clear all cached entries and clean up temp files. Thread-safe."""
        with self._lock:
            for key in list(self._cache.keys()):
                self._remove_entry(key)

            self._cache.clear()
            self._temp_files.clear()

            # Clear persisted cache
            if self.persist_path and os.path.exists(self.persist_path):
                try:
                    os.unlink(self.persist_path)
                except OSError:
                    pass

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics. Thread-safe."""
        with self._lock:
            total_size = 0
            for temp_path in set(self._temp_files.values()):
                try:
                    total_size += os.path.getsize(temp_path)
                except OSError:
                    pass

            return {
                'entries': len(self._cache),
                'max_size': self.max_size,
                'total_bytes': total_size,
                'persist_enabled': self.persist_path is not None
            }

    def _persist(self) -> None:
        """Persist cache to disk if configured. Uses JSON for security."""
        if not self.persist_path:
            return

        try:
            # Create directory if needed
            cache_dir = os.path.dirname(self.persist_path)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)

            # Prepare cache data for JSON serialization
            cache_data = {
                'version': 1,
                'entries': self._cache
            }

            # Save cache as JSON
            with open(self.persist_path, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except (OSError, TypeError) as e:
            print(f"Warning: Could not persist cache to {self.persist_path}: {e}")

    def cleanup(self) -> None:
        """Cleanup temp files on exit. Thread-safe."""
        with self._lock:
            # Only cleanup files that are not persisted
            if not self.persist_path:
                for temp_path in set(self._temp_files.values()):
                    try:
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)
                    except OSError:
                        pass


class Display:
    """
    Display class for interacting with the CM5 e-ink display system.

    This class provides functionality to:
    - Display PNG images on the e-ink screen
    - Display raw 1-bit image data
    - Clear the display
    - Control display refresh modes
    - Manage display power states
    - Cache converted images for improved performance

    Thread-safe implementation with singleton pattern option.
    """

    # Display constants (will be updated dynamically)
    WIDTH = 128  # Default, will be updated after initialization
    HEIGHT = 250  # Default, will be updated after initialization
    ARRAY_SIZE = (128 * 250) // 8  # Default, will be updated after initialization

    # Shared resources with thread safety
    _cache_manager: ImageCacheManager | None = None
    _cache_lock = threading.Lock()

    # Security: Allowed directories for image access
    _allowed_dirs: list[str] = [
        os.path.expanduser("~"),
        "/tmp",
        tempfile.gettempdir(),
        "/opt/distiller-cm5-sdk",
    ]

    def __init__(self, library_path: str | None = None, auto_init: bool = True,
                 enable_cache: bool = True, cache_size: int = 100,
                 cache_persist_path: str | None = None,
                 allowed_dirs: list[str] | None = None):
        """
        Initialize the Display object.

        Args:
            library_path: Optional path to the shared library. If None, searches common locations.
            auto_init: Whether to automatically initialize the display hardware
            enable_cache: Whether to enable image caching
            cache_size: Maximum number of cached entries
            cache_persist_path: Optional path to persist cache between sessions
            allowed_dirs: Optional list of allowed directories for image access

        Raises:
            DisplayError: If library can't be loaded or display can't be initialized
        """
        self._lib = None
        self._initialized = False

        # Set allowed directories
        if allowed_dirs:
            self._allowed_dirs = [os.path.abspath(d) for d in allowed_dirs]

        # Initialize cache manager if enabled (thread-safe)
        if enable_cache:
            with Display._cache_lock:
                if Display._cache_manager is None:
                    # Default persist path if not specified
                    if cache_persist_path is None:
                        cache_dir = os.path.expanduser("~/.cache/distiller_eink")
                        cache_persist_path = os.path.join(cache_dir, "image_cache.json")

                    Display._cache_manager = ImageCacheManager(
                        max_size=cache_size,
                        persist_path=cache_persist_path
                    )

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
            "Could not find libdistiller_display_sdk_shared.so in any of these locations:\n" +
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

        # New image processing functions (optional - may not exist in older libraries)
        try:
            # process_image_auto(filename, output_data, scaling, dithering, rotate, flip, crop_x, crop_y) -> bool
            self._lib.process_image_auto.restype = c_bool
            self._lib.process_image_auto.argtypes = [
                c_char_p, ctypes.POINTER(ctypes.c_ubyte),
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int
            ]

            # is_image_format_supported(filename) -> bool
            self._lib.is_image_format_supported.restype = c_bool
            self._lib.is_image_format_supported.argtypes = [c_char_p]

            # get_supported_image_formats(formats, max_len) -> bool
            self._lib.get_supported_image_formats.restype = c_bool
            self._lib.get_supported_image_formats.argtypes = [ctypes.c_char_p, c_uint32]

            self._rust_processing_available = True
        except AttributeError:
            # Rust image processing not available
            self._rust_processing_available = False

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

            # Update instance variables only, not class variables
            self.WIDTH = width_ptr.contents.value
            self.HEIGHT = height_ptr.contents.value
            self.ARRAY_SIZE = (self.WIDTH * self.HEIGHT) // 8

        except (AttributeError, TypeError, OSError) as e:
            # Use class defaults if library call fails
            self.WIDTH = Display.WIDTH
            self.HEIGHT = Display.HEIGHT
            self.ARRAY_SIZE = Display.ARRAY_SIZE
            print(f"Warning: Could not get dimensions from library: {e}")

    def get_dimensions(self) -> tuple[int, int]:
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
            except (AttributeError, TypeError, OSError):
                return (self.WIDTH, self.HEIGHT)
        return (self.WIDTH, self.HEIGHT)

    def _validate_path(self, path: str) -> None:
        """
        Validate that a file path is safe and within allowed directories.

        Args:
            path: Path to validate

        Raises:
            DisplayError: If path is unsafe or outside allowed directories
        """
        # Resolve the absolute path
        abs_path = os.path.abspath(path)

        # Check for path traversal attempts
        if ".." in path or "~" in path:
            # Expand and resolve to catch traversal attempts
            resolved_path = os.path.realpath(os.path.expanduser(path))
            if resolved_path != abs_path:
                raise DisplayError(f"Path traversal detected: {path}")

        # Check if path is within allowed directories
        path_allowed = False
        for allowed_dir in self._allowed_dirs:
            allowed_abs = os.path.abspath(allowed_dir)
            if abs_path.startswith(allowed_abs):
                path_allowed = True
                break

        if not path_allowed:
            raise DisplayError(f"Path outside allowed directories: {path}")

    def display_image(self, image: str | bytes, mode: DisplayMode = DisplayMode.FULL, rotate: bool = False, flip_horizontal: bool = False, invert_colors: bool = False, src_width: int = None, src_height: int = None) -> None:
        """
        Display an image on the e-ink screen.

        Args:
            image: Either a PNG file path (string) or raw 1-bit image data (bytes)
            mode: Display refresh mode
            rotate: If True, rotate landscape data (250x128) to portrait (128x250)
            flip_horizontal: If True, mirror the image horizontally (left-right)
            invert_colors: If True, invert colors (black↔white)
            src_width: Source width in pixels (required when transforming raw data)
            src_height: Source height in pixels (required when transforming raw data)

        Raises:
            DisplayError: If display operation fails or path is unsafe
        """
        if not self._initialized:
            raise DisplayError("Display not initialized. Call initialize() first.")

        if isinstance(image, str):
            # Validate file path for security
            self._validate_path(image)
            # PNG file path
            self._display_png(image, mode, rotate, flip_horizontal, invert_colors)
        elif isinstance(image, bytes | bytearray):
            # Raw image data
            raw_data = bytes(image)

            if flip_horizontal or rotate or invert_colors:
                if src_width is None or src_height is None:
                    raise DisplayError("src_width and src_height are required when transforming raw data")

                # Apply transformations in DistillerGUI order: flip, rotate, then invert colors
                if flip_horizontal:
                    raw_data = flip_bitpacked_horizontal(raw_data, src_width, src_height)

                if rotate:
                    # If we flipped, dimensions stay the same for rotation
                    raw_data = rotate_bitpacked_ccw_90(raw_data, src_width, src_height)

                if invert_colors:
                    raw_data = invert_bitpacked_colors(raw_data)

            self._display_raw(raw_data, mode)
        else:
            raise DisplayError(f"Invalid image type: {type(image)}. Expected str or bytes.")

    def _display_png(self, filename: str, mode: DisplayMode, rotate: bool = False, flip_horizontal: bool = False, invert_colors: bool = False) -> None:
        """Display a PNG image file."""
        # Path already validated in display_image()
        if not os.path.exists(filename):
            raise DisplayError(f"PNG file not found: {filename}")

        if rotate or flip_horizontal or invert_colors:
            # For PNG transformations, convert to raw data first
            raw_data = self.convert_png_to_raw(filename)
            # Assume PNG is 250x128 landscape format when transforming

            # Apply transformations in DistillerGUI order: flip, rotate, then invert colors
            if flip_horizontal:
                raw_data = flip_bitpacked_horizontal(raw_data, 250, 128)

            if rotate:
                raw_data = rotate_bitpacked_ccw_90(raw_data, 250, 128)

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

    def convert_png_to_raw(self, filename: str) -> bytes:
        """
        Convert PNG file to raw 1-bit data.

        Args:
            filename: Path to PNG file (must be exactly 128x250 pixels)

        Returns:
            Raw 1-bit packed image data (4000 bytes)

        Raises:
            DisplayError: If conversion fails or path is unsafe
        """
        # Validate path for security
        self._validate_path(filename)

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

    def set_firmware(self, firmware_type: str | FirmwareType) -> None:
        """
        Set the default firmware type for the display.

        Args:
            firmware_type: Firmware type string (e.g., "EPD128x250", "EPD240x416")

        Raises:
            DisplayError: If firmware type is invalid or setting fails
        """
        if not (hasattr(self, '_config_available') and self._config_available):
            raise DisplayError("Configuration system not available. Please rebuild the Rust library.")

        if isinstance(firmware_type, FirmwareType):
            firmware_str = firmware_type.value
        else:
            firmware_str = firmware_type
        firmware_bytes = firmware_str.encode('utf-8')
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

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the image conversion cache. Thread-safe."""
        with cls._cache_lock:
            if cls._cache_manager:
                cls._cache_manager.clear()

    @classmethod
    def get_cache_stats(cls) -> dict[str, Any]:
        """Get cache statistics. Thread-safe."""
        with cls._cache_lock:
            if cls._cache_manager:
                return cls._cache_manager.get_stats()
            return {'entries': 0, 'max_size': 0, 'total_bytes': 0, 'persist_enabled': False}

    def _get_display_dimensions(self) -> tuple[int, int]:
        """Get current display dimensions."""
        if not self._initialized:
            self.initialize()
        return self.WIDTH, self.HEIGHT

    def _convert_image_rust(self, image_path: str, scaling: ScalingMethod = ScalingMethod.LETTERBOX,
                           dithering: DitheringMethod = DitheringMethod.FLOYD_STEINBERG,
                           rotate: bool = False, flop: bool = False,
                           crop_x: int | None = None, crop_y: int | None = None) -> bytes:
        """
        Convert image using Rust processing (faster, supports more formats).

        Returns:
            Raw 1-bit packed image data
        """
        # Path already validated by caller
        if not os.path.exists(image_path):
            raise DisplayError(f"Image file not found: {image_path}")

        # Create output buffer
        output_data = (ctypes.c_ubyte * self.ARRAY_SIZE)()
        filename_bytes = image_path.encode('utf-8')

        # Convert None to -1 for crop coordinates
        crop_x_val = -1 if crop_x is None else crop_x
        crop_y_val = -1 if crop_y is None else crop_y

        success = self._lib.process_image_auto(
            filename_bytes, output_data,
            int(scaling), int(dithering),
            int(rotate), int(flop),
            crop_x_val, crop_y_val
        )

        if not success:
            raise DisplayError(f"Failed to process image: {image_path}")

        return bytes(output_data)

    def is_format_supported(self, image_path: str) -> bool:
        """
        Check if an image format is supported.

        Args:
            image_path: Path to image file

        Returns:
            True if format is supported
        """
        if not hasattr(self, '_rust_processing_available') or not self._rust_processing_available:
            # Fallback to PNG only
            return image_path.lower().endswith('.png')

        filename_bytes = image_path.encode('utf-8')
        return bool(self._lib.is_image_format_supported(filename_bytes))

    def get_supported_formats(self) -> list[str]:
        """
        Get list of supported image formats.

        Returns:
            List of supported file extensions
        """
        if not hasattr(self, '_rust_processing_available') or not self._rust_processing_available:
            return ['png']

        buffer = ctypes.create_string_buffer(256)
        success = self._lib.get_supported_image_formats(buffer, 256)

        if success:
            formats_str = buffer.value.decode('utf-8')
            return formats_str.split(',')

        return ['png']

    def _convert_png_auto(self, image_path: str, scaling: ScalingMethod = ScalingMethod.LETTERBOX,
                         dithering: DitheringMethod = DitheringMethod.FLOYD_STEINBERG,
                         rotate: bool = False, flop: bool = False,
                         crop_x: int | None = None, crop_y: int | None = None) -> str:
        """
        Convert any image to display-compatible format with caching support.
        Now supports multiple image formats via Rust processing.

        Args:
            image_path: Path to source image file (PNG, JPEG, BMP, TIFF, WebP, etc.)
            scaling: How to scale the image to fit display
            dithering: Dithering method for 1-bit conversion
            rotate: If True, rotate image 90 degrees counter-clockwise
            flop: If True, flip image horizontally (left-right mirror)
            crop_x: X position for crop when using CROP_CENTER (None = center)
            crop_y: Y position for crop when using CROP_CENTER (None = center)

        Returns:
            Path to converted temporary PNG file

        Raises:
            DisplayError: If conversion fails or path is unsafe
        """
        # Validate path for security
        self._validate_path(image_path)

        if not os.path.exists(image_path):
            raise DisplayError(f"Image file not found: {image_path}")

        # Get display dimensions
        display_width, display_height = self._get_display_dimensions()

        # Check cache first
        if Display._cache_manager:
            cached_path = Display._cache_manager.get(
                image_path, display_width, display_height,
                int(scaling), int(dithering), rotate, flop, crop_x, crop_y
            )
            if cached_path:
                return cached_path

        # Try Rust processing first if available (faster and supports more formats)
        if hasattr(self, '_rust_processing_available') and self._rust_processing_available:
            try:
                # Get raw data from Rust processing
                raw_data = self._convert_image_rust(
                    image_path, scaling, dithering, rotate, flop, crop_x, crop_y
                )

                # Save to temporary PNG file
                temp_fd, temp_path = tempfile.mkstemp(suffix='.png', prefix='eink_auto_')
                try:
                    os.close(temp_fd)

                    # Convert raw data to PIL Image for saving as PNG
                    img_array = []
                    for byte_idx in range(len(raw_data)):
                        byte_val = raw_data[byte_idx]
                        for bit_idx in range(8):
                            bit = (byte_val >> (7 - bit_idx)) & 1
                            img_array.append(255 if bit else 0)

                    # Trim to exact size
                    img_array = img_array[:display_width * display_height]

                    # Create PIL image from array
                    img = Image.new('L', (display_width, display_height))
                    img.putdata(img_array)
                    img = img.convert('1')
                    img.save(temp_path, 'PNG')

                    # Store in cache
                    if Display._cache_manager:
                        Display._cache_manager.put(
                            image_path, display_width, display_height,
                            int(scaling), int(dithering), rotate, flop, crop_x, crop_y,
                            temp_path
                        )

                    return temp_path

                except Exception as e:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass  # Cleanup error is secondary to the main error
                    raise DisplayError(f"Failed to save converted image: {e}")

            except Exception as rust_error:
                # Fall back to PIL processing
                print(f"Rust processing failed, falling back to PIL: {rust_error}")

        try:
            # Load and process the image
            with Image.open(image_path) as img:
                # Convert to RGB if needed (handles RGBA, palette, etc.)
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')

                # Apply transformations (rotate, flop)
                if flop:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                if rotate:
                    img = img.transpose(Image.ROTATE_90)

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

                    # Store in cache
                    if Display._cache_manager:
                        Display._cache_manager.put(
                            image_path, display_width, display_height,
                            int(scaling), int(dithering), rotate, flop, crop_x, crop_y,
                            temp_path
                        )

                    return temp_path
                except Exception as e:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass  # Cleanup error is secondary to the main error
                    raise DisplayError(f"Failed to save converted image: {e}")

        except Exception as e:
            raise DisplayError(f"Failed to convert PNG: {e}")

    def _scale_image(self, img: Image.Image, target_width: int, target_height: int,
                    scaling: ScalingMethod, crop_x: int | None = None,
                    crop_y: int | None = None) -> Image.Image:
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
                        rotate: bool = False, flop: bool = False,
                        crop_x: int | None = None, crop_y: int | None = None,
                        cleanup_temp: bool = True) -> bool:
        """
        Display any image with automatic conversion to display specifications.
        Supports multiple formats: PNG, JPEG, GIF, BMP, TIFF, WebP, ICO, PNM, TGA, DDS

        Args:
            image_path: Path to source image file (any supported format)
            mode: Display refresh mode
            scaling: How to scale the image to fit display
            dithering: Dithering method for 1-bit conversion
            rotate: If True, rotate image 90 degrees counter-clockwise
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
            raise DisplayError(f"Failed to auto-display image: {e}")

        finally:
            # Cleanup temporary file (only if not cached)
            if cleanup_temp and temp_path and os.path.exists(temp_path):
                # Don't delete if it's in cache
                if not Display._cache_manager or temp_path not in Display._cache_manager._temp_files.values():
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass  # Ignore cleanup errors

    def display_image_auto(self, image_path: str, mode: DisplayMode = DisplayMode.FULL,
                          scaling: ScalingMethod = ScalingMethod.LETTERBOX,
                          dithering: DitheringMethod = DitheringMethod.FLOYD_STEINBERG,
                          rotate: bool = False, flop: bool = False,
                          crop_x: int | None = None, crop_y: int | None = None) -> bool:
        """
        Alias for display_png_auto that better reflects multi-format support.
        """
        return self.display_png_auto(image_path, mode, scaling, dithering, rotate, flop, crop_x, crop_y)


# Convenience functions for simple usage (following SDK pattern)
def display_png(filename: str, mode: DisplayMode = DisplayMode.FULL, rotate: bool = False,
                auto_convert: bool = False, scaling: ScalingMethod = ScalingMethod.LETTERBOX,
                dithering: DitheringMethod = DitheringMethod.FLOYD_STEINBERG,
                flop: bool = False, crop_x: int | None = None, crop_y: int | None = None) -> None:
    """
    Convenience function to display a PNG image.

    Args:
        filename: Path to PNG file
        mode: Display refresh mode
        rotate: If True, rotate landscape PNG (250x128) to portrait (128x250)
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
                    rotate: bool = False, flop: bool = False,
                    crop_x: int | None = None, crop_y: int | None = None) -> None:
    """
    Convenience function to display any PNG image with automatic conversion.

    Args:
        filename: Path to PNG file (any size, any format)
        mode: Display refresh mode
        scaling: How to scale the image to fit display
        dithering: Dithering method for 1-bit conversion
        rotate: If True, rotate image 90 degrees counter-clockwise
        flop: If True, flip image horizontally (left-right mirror)
        crop_x: X position for crop when using CROP_CENTER (None = center)
        crop_y: Y position for crop when using CROP_CENTER (None = center)
    """
    with Display() as display:
        display.display_png_auto(filename, mode, scaling, dithering, rotate, flop, crop_x, crop_y)


def display_image_auto(filename: str, mode: DisplayMode = DisplayMode.FULL,
                       scaling: ScalingMethod = ScalingMethod.LETTERBOX,
                       dithering: DitheringMethod = DitheringMethod.FLOYD_STEINBERG,
                       rotate: bool = False, flop: bool = False,
                       crop_x: int | None = None, crop_y: int | None = None) -> None:
    """
    Display any supported image format with automatic conversion.
    Supports: PNG, JPEG, GIF, BMP, TIFF, WebP, ICO, PNM, TGA, DDS

    Args:
        filename: Path to image file (any supported format)
        mode: Display refresh mode
        scaling: How to scale the image to fit display
        dithering: Dithering method for 1-bit conversion
        rotate: If True, rotate image 90 degrees counter-clockwise
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
    # Create a temporary display instance to get actual dimensions
    try:
        with Display(auto_init=False) as display:
            width, height = display.get_dimensions()
            array_size = (width * height) // 8
    except Exception:
        # Fall back to class defaults
        width = Display.WIDTH
        height = Display.HEIGHT
        array_size = Display.ARRAY_SIZE

    return {
        "width": width,
        "height": height,
        "data_size": array_size,
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
def set_default_firmware(firmware_type: str | FirmwareType) -> None:
    """
    Set the default firmware type globally.

    Args:
        firmware_type: Firmware type (e.g., FirmwareType.EPD128x250, FirmwareType.EPD240x416 or string)

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
