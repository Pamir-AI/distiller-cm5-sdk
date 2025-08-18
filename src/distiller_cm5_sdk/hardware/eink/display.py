#!/usr/bin/env python3
"""E-ink display control and image display."""

import ctypes
import hashlib
import json
import logging
import os
import tempfile
import threading
import weakref
from ctypes import POINTER, c_bool, c_char_p, c_uint32
from enum import Enum, IntEnum
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)


class DisplayConstants:
    """Display configuration constants."""

    FIRMWARE_BUFFER_SIZE = 64
    FORMATS_BUFFER_SIZE = 256
    DEFAULT_CACHE_SIZE = 100
    MAX_RETRIES = 5
    RETRY_DELAY = 0.5
    # Grayscale conversion weights
    GRAYSCALE_R_WEIGHT = 77
    GRAYSCALE_G_WEIGHT = 151
    GRAYSCALE_B_WEIGHT = 30


class DisplayError(Exception):
    """Display operation error."""

    pass


class DisplayMode(IntEnum):
    """Display refresh modes."""

    FULL = 0  # Full refresh
    PARTIAL = 1  # Partial refresh


class FirmwareType(Enum):
    """E-ink firmware types."""

    EPD128x250 = "EPD128x250"
    EPD240x416 = "EPD240x416"


class ScalingMethod(IntEnum):
    """Image scaling methods."""

    LETTERBOX = 0  # Maintain aspect ratio
    CROP_CENTER = 1  # Center crop
    STRETCH = 2  # Stretch to fill


class DitheringMethod(IntEnum):
    """Dithering methods."""

    NONE = 0
    FLOYD_STEINBERG = 1
    SIERRA = 2
    SIERRA_2ROW = 3
    SIERRA_LITE = 4
    SIMPLE = 5  # Legacy


class RotationMode(IntEnum):
    """Rotation modes."""

    NONE = 0
    ROTATE_90 = 1  # 90° CW
    ROTATE_180 = 2  # 180°
    ROTATE_270 = 3  # 270° CW


class ImageCacheManager:
    """Thread-safe LRU cache for converted images."""

    _lock = threading.RLock()

    def __init__(
        self, max_size: int = DisplayConstants.DEFAULT_CACHE_SIZE, persist_path: str | None = None
    ):
        self.max_size = max_size
        self.persist_path = persist_path
        self._cache: dict[str, dict[str, Any]] = {}
        self._temp_files: dict[str, str] = {}  # Track temp files for cleanup
        self._finalizer = None

        if persist_path and os.path.exists(persist_path):
            self._load_cache_from_json(persist_path)
        self._finalizer = weakref.finalize(
            self, self._cleanup_static, list(self._temp_files.values())
        )

    def _load_cache_from_json(self, persist_path: str) -> None:
        try:
            with open(persist_path) as f:
                saved_cache = json.load(f)

                # Validate cache structure and version
                if not isinstance(saved_cache, dict):
                    return

                cache_version = saved_cache.get("version", 0)
                if cache_version != 1:
                    return

                entries = saved_cache.get("entries", {})
                for key, entry in entries.items():
                    # Validate entry structure
                    if not self._validate_cache_entry(entry):
                        continue

                    # Check if temp file still exists
                    if "temp_path" in entry and os.path.exists(entry["temp_path"]):
                        self._cache[key] = entry
                        self._temp_files[key] = entry["temp_path"]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Warning: Could not load cache from {persist_path}: {e}")

    def _validate_cache_entry(self, entry: Any) -> bool:
        if not isinstance(entry, dict):
            return False

        required_keys = ["temp_path", "source_path", "params"]
        if not all(key in entry for key in required_keys):
            return False

        # Validate temp_path is within allowed directory
        temp_path = entry.get("temp_path", "")
        if not temp_path.startswith(tempfile.gettempdir()):
            return False

        return True

    @staticmethod
    def _cleanup_static(temp_files: list[str]) -> None:
        for temp_path in temp_files:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except OSError:
                pass

    def _generate_cache_key(
        self,
        image_path: str,
        display_width: int,
        display_height: int,
        scaling: int,
        dithering: int,
        rotation: int,
        h_flip: bool,
        v_flip: bool,
        crop_x: int | None,
        crop_y: int | None,
    ) -> str:
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
            "path": image_path,
            "mtime": mtime,
            "width": display_width,
            "height": display_height,
            "scaling": scaling,
            "dithering": dithering,
            "rotation": rotation,
            "h_flip": h_flip,
            "v_flip": v_flip,
            "crop_x": crop_x,
            "crop_y": crop_y,
        }

        # Generate hash of the key data
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def get(
        self,
        image_path: str,
        display_width: int,
        display_height: int,
        scaling: int,
        dithering: int,
        rotation: int,
        h_flip: bool,
        v_flip: bool,
        crop_x: int | None,
        crop_y: int | None,
    ) -> str | None:
        with self._lock:
            key = self._generate_cache_key(
                image_path,
                display_width,
                display_height,
                scaling,
                dithering,
                rotation,
                h_flip,
                v_flip,
                crop_x,
                crop_y,
            )

            if key in self._cache:
                entry = self._cache[key]
                # Verify the temp file still exists
                if os.path.exists(entry["temp_path"]):
                    # Move to end (most recently used)
                    self._cache.pop(key)
                    self._cache[key] = entry
                    return entry["temp_path"]
                else:
                    # Clean up invalid entry
                    self._cache.pop(key, None)
                    self._temp_files.pop(key, None)

            return None

    def put(
        self,
        image_path: str,
        display_width: int,
        display_height: int,
        scaling: int,
        dithering: int,
        rotation: int,
        h_flip: bool,
        v_flip: bool,
        crop_x: int | None,
        crop_y: int | None,
        temp_path: str,
    ) -> None:
        with self._lock:
            # Validate temp_path is in temp directory
            if not temp_path.startswith(tempfile.gettempdir()):
                raise ValueError(f"Invalid temp path: {temp_path}")

            key = self._generate_cache_key(
                image_path,
                display_width,
                display_height,
                scaling,
                dithering,
                rotation,
                h_flip,
                v_flip,
                crop_x,
                crop_y,
            )

            # Enforce max size (remove oldest entries)
            while len(self._cache) >= self.max_size:
                # Remove oldest (first) entry
                oldest_key = next(iter(self._cache))
                self._remove_entry(oldest_key)

            # Add new entry
            self._cache[key] = {
                "temp_path": temp_path,
                "source_path": image_path,
                "params": {
                    "width": display_width,
                    "height": display_height,
                    "scaling": scaling,
                    "dithering": dithering,
                    "rotation": rotation,
                    "h_flip": h_flip,
                    "v_flip": v_flip,
                    "crop_x": crop_x,
                    "crop_y": crop_y,
                },
            }
            self._temp_files[key] = temp_path

            # Update finalizer with new temp files list
            if self._finalizer:
                self._finalizer.detach()
            self._finalizer = weakref.finalize(
                self, self._cleanup_static, list(self._temp_files.values())
            )

            # Persist cache if configured
            self._persist()

    def _remove_entry(self, key: str) -> None:
        self._cache.pop(key, None)
        temp_path = self._temp_files.pop(key, None)

        # Clean up temp file if it exists and is not used elsewhere
        if temp_path and temp_path not in self._temp_files.values():
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    def clear(self) -> None:
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
        with self._lock:
            total_size = 0
            for temp_path in set(self._temp_files.values()):
                try:
                    total_size += os.path.getsize(temp_path)
                except OSError:
                    pass

            return {
                "entries": len(self._cache),
                "max_size": self.max_size,
                "total_bytes": total_size,
                "persist_enabled": self.persist_path is not None,
            }

    def _persist(self) -> None:
        if not self.persist_path:
            return

        try:
            # Create directory if needed
            cache_dir = os.path.dirname(self.persist_path)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)

            # Prepare cache data for JSON serialization
            cache_data = {"version": 1, "entries": self._cache}

            # Save cache as JSON
            with open(self.persist_path, "w") as f:
                json.dump(cache_data, f, indent=2)
        except (OSError, TypeError) as e:
            print(f"Warning: Could not persist cache to {self.persist_path}: {e}")

    def cleanup(self) -> None:
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
    """E-ink display interface."""

    WIDTH = None
    HEIGHT = None
    ARRAY_SIZE = None

    _cache_manager: ImageCacheManager | None = None
    _cache_lock = threading.Lock()
    _allowed_dirs: list[str] = [
        os.path.expanduser("~"),
        "/tmp",
        tempfile.gettempdir(),
        "/opt/distiller-cm5-sdk",
    ]

    def __init__(
        self,
        library_path: str | None = None,
        auto_init: bool = True,
        enable_cache: bool = True,
        cache_size: int = DisplayConstants.DEFAULT_CACHE_SIZE,
        cache_persist_path: str | None = None,
        allowed_dirs: list[str] | None = None,
    ):
        self._lib = None
        self._initialized = False

        # Set allowed directories
        if allowed_dirs:
            self._allowed_dirs = [os.path.abspath(d) for d in allowed_dirs]

        if enable_cache:
            with Display._cache_lock:
                if Display._cache_manager is None:
                    if cache_persist_path is None:
                        cache_dir = os.path.expanduser("~/.cache/distiller_eink")
                        cache_persist_path = os.path.join(cache_dir, "image_cache.json")

                    Display._cache_manager = ImageCacheManager(
                        max_size=cache_size, persist_path=cache_persist_path
                    )

        if library_path is None:
            library_path = self._find_library()

        if not os.path.exists(library_path):
            raise DisplayError(f"Display library not found: {library_path}")

        try:
            self._lib = ctypes.CDLL(library_path)
        except OSError as e:
            raise DisplayError(f"Failed to load display library: {e}")

        self._setup_function_signatures()

        if auto_init:
            self.initialize()

    def _find_library(self) -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
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
            "Could not find libdistiller_display_sdk_shared.so in any of these locations:\n"
            + "\n".join(f"  - {path}" for path in search_paths)
        )

    def _setup_function_signatures(self):
        # display_init() -> bool
        self._lib.display_init.restype = c_bool
        self._lib.display_init.argtypes = []

        # display_image_raw(const uint8_t* data, display_mode_t mode) -> bool
        self._lib.display_image_raw.restype = c_bool
        self._lib.display_image_raw.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int]

        # display_image_file(const char* filename, display_mode_t mode) -> bool
        self._lib.display_image_file.restype = c_bool
        self._lib.display_image_file.argtypes = [c_char_p, ctypes.c_int]

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

        # convert_image_to_1bit(const char* filename, uint8_t* output_data) -> bool
        self._lib.convert_image_to_1bit.restype = c_bool
        self._lib.convert_image_to_1bit.argtypes = [c_char_p, ctypes.POINTER(ctypes.c_ubyte)]

        # Configuration functions (required)
        self._lib.display_set_firmware.restype = c_bool
        self._lib.display_set_firmware.argtypes = [c_char_p]

        self._lib.display_get_firmware.restype = c_bool
        self._lib.display_get_firmware.argtypes = [ctypes.c_char_p, c_uint32]

        self._lib.display_initialize_config.restype = c_bool
        self._lib.display_initialize_config.argtypes = []

        # Image processing functions (required)
        self._lib.process_image_auto.restype = c_bool
        self._lib.process_image_auto.argtypes = [
            c_char_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int,  # scaling
            ctypes.c_int,  # dithering
            ctypes.c_int,  # rotation
            ctypes.c_int,  # h_flip
            ctypes.c_int,  # v_flip
            ctypes.c_int,  # crop_x
            ctypes.c_int,  # crop_y
        ]

        self._lib.is_image_format_supported.restype = c_bool
        self._lib.is_image_format_supported.argtypes = [c_char_p]

        self._lib.get_supported_image_formats.restype = c_bool
        self._lib.get_supported_image_formats.argtypes = [ctypes.c_char_p, c_uint32]

    def initialize(self) -> None:
        if self._initialized:
            return

        # Initialize configuration system (required)
        config_success = self._lib.display_initialize_config()
        if not config_success:
            raise DisplayError(
                "Failed to initialize display configuration. "
                "Set DISTILLER_EINK_FIRMWARE environment variable to "
                "'EPD128x250' or 'EPD240x416', or create /opt/distiller-cm5-sdk/eink.conf"
            )

        success = self._lib.display_init()
        if not success:
            raise DisplayError("Failed to initialize display hardware")

        # Update dimensions based on current firmware
        self._update_dimensions()

        self._initialized = True

    def _update_dimensions(self) -> None:
        try:
            width_ptr = ctypes.pointer(c_uint32())
            height_ptr = ctypes.pointer(c_uint32())
            self._lib.display_get_dimensions(width_ptr, height_ptr)

            # Update instance variables only, not class variables
            self.WIDTH = width_ptr.contents.value
            self.HEIGHT = height_ptr.contents.value
            self.ARRAY_SIZE = (self.WIDTH * self.HEIGHT) // 8

            # Also update class variables if they were None
            if Display.WIDTH is None:
                Display.WIDTH = self.WIDTH
                Display.HEIGHT = self.HEIGHT
                Display.ARRAY_SIZE = self.ARRAY_SIZE

        except (AttributeError, TypeError, OSError) as e:
            raise DisplayError(
                f"Failed to get display dimensions from library: {e}. "
                "Ensure DISTILLER_EINK_FIRMWARE environment variable is set."
            )

    def get_dimensions(self) -> tuple[int, int]:
        if not self._initialized:
            # Try to get dimensions without initializing
            try:
                width_ptr = ctypes.pointer(c_uint32())
                height_ptr = ctypes.pointer(c_uint32())
                self._lib.display_get_dimensions(width_ptr, height_ptr)
                return (width_ptr.contents.value, height_ptr.contents.value)
            except (AttributeError, TypeError, OSError):
                if self.WIDTH is None or self.HEIGHT is None:
                    raise DisplayError(
                        "Display dimensions not configured. "
                        "Set DISTILLER_EINK_FIRMWARE environment variable to "
                        "'EPD128x250' or 'EPD240x416', or create /opt/distiller-cm5-sdk/eink.conf"
                    )
                return (self.WIDTH, self.HEIGHT)
        return (self.WIDTH, self.HEIGHT)

    def _validate_path(self, path: str) -> None:
        """Validate file path is safe and within allowed directories."""
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

    def display_image(
        self,
        image: str | bytes,
        mode: DisplayMode = DisplayMode.FULL,
        scaling: ScalingMethod = ScalingMethod.LETTERBOX,
        dithering: DitheringMethod = DitheringMethod.FLOYD_STEINBERG,
        rotation: RotationMode = RotationMode.NONE,
        h_flip: bool = False,
        v_flip: bool = False,
        invert_colors: bool = False,
        crop_x: int | None = None,
        crop_y: int | None = None,
        src_width: int | None = None,
        src_height: int | None = None,
    ) -> None:
        """
        Display an image on the e-ink screen.

        Args:
            image: Either an image file path (string) or raw 1-bit image data (bytes)
            mode: Display refresh mode
            scaling: How to scale the image (for file paths only)
            dithering: Dithering method for 1-bit conversion (for file paths only)
            rotation: Rotation mode (NONE, ROTATE_90, ROTATE_180, ROTATE_270)
            h_flip: If True, mirror the image horizontally (left-right)
            v_flip: If True, mirror the image vertically (top-bottom)
            invert_colors: If True, invert colors (black↔white)
            crop_x: X position for crop when using CROP_CENTER (None = center)
            crop_y: Y position for crop when using CROP_CENTER (None = center)
            src_width: Source width in pixels (required when transforming raw data)
            src_height: Source height in pixels (required when transforming raw data)

        Raises:
            DisplayError: If display operation fails or path is unsafe
        """
        if not self._initialized:
            self.reacquire_hardware()

        if isinstance(image, str):
            # Validate file path for security
            self._validate_path(image)

            # Check if we need to convert the image
            needs_conversion = (
                scaling != ScalingMethod.LETTERBOX
                or dithering != DitheringMethod.FLOYD_STEINBERG
                or crop_x is not None
                or crop_y is not None
                or not image.lower().endswith(".png")
            )

            if needs_conversion:
                # Convert image with specified settings
                temp_path = self._convert_image_auto(
                    image, scaling, dithering, rotation, h_flip, v_flip, crop_x, crop_y
                )
                try:
                    # Display the converted image (no additional transformations needed)
                    self._display_image_file(
                        temp_path, mode, RotationMode.NONE, False, False, invert_colors
                    )
                finally:
                    # Clean up temp file if not cached
                    if temp_path and os.path.exists(temp_path):
                        if (
                            not Display._cache_manager
                            or temp_path not in Display._cache_manager._temp_files.values()
                        ):
                            try:
                                os.unlink(temp_path)
                            except OSError:
                                pass
            else:
                # Direct display for PNG files
                self._display_image_file(image, mode, rotation, h_flip, v_flip, invert_colors)
        elif isinstance(image, bytes | bytearray):
            # Raw image data
            raw_data = bytes(image)

            if h_flip or v_flip or rotation != RotationMode.NONE or invert_colors:
                if src_width is None or src_height is None:
                    raise DisplayError(
                        "src_width and src_height are required when transforming raw data"
                    )

                # Apply transformations in order
                if h_flip:
                    raw_data = transform_bitpacked(
                        raw_data, src_width, src_height, TransformOperation.FLIP_H
                    )
                if v_flip:
                    raw_data = transform_bitpacked(
                        raw_data, src_width, src_height, TransformOperation.FLIP_V
                    )
                if rotation == RotationMode.ROTATE_90:
                    raw_data = transform_bitpacked(
                        raw_data, src_width, src_height, TransformOperation.ROTATE_90_CW
                    )
                    # Update dimensions after rotation
                    src_width, src_height = src_height, src_width
                elif rotation == RotationMode.ROTATE_180:
                    raw_data = transform_bitpacked(
                        raw_data, src_width, src_height, TransformOperation.ROTATE_180
                    )
                elif rotation == RotationMode.ROTATE_270:
                    raw_data = transform_bitpacked(
                        raw_data, src_width, src_height, TransformOperation.ROTATE_90_CCW
                    )
                    # Update dimensions after rotation
                    src_width, src_height = src_height, src_width
                if invert_colors:
                    raw_data = transform_bitpacked(
                        raw_data, src_width, src_height, TransformOperation.INVERT
                    )

            self._display_raw(raw_data, mode)
        else:
            raise DisplayError(f"Invalid image type: {type(image)}. Expected str or bytes.")

    def _display_image_file(
        self,
        filename: str,
        mode: DisplayMode,
        rotation: RotationMode = RotationMode.NONE,
        h_flip: bool = False,
        v_flip: bool = False,
        invert_colors: bool = False,
    ) -> None:
        """Display an image file."""
        # Path already validated in display_image()
        if not os.path.exists(filename):
            raise DisplayError(f"Image file not found: {filename}")

        if rotation != RotationMode.NONE or h_flip or v_flip or invert_colors:
            # For image transformations, convert to raw data first
            raw_data = self.convert_image_to_raw(filename)
            # Assume image is 250x128 landscape format when transforming
            src_width, src_height = 250, 128

            # Apply transformations
            if h_flip:
                raw_data = transform_bitpacked(
                    raw_data, src_width, src_height, TransformOperation.FLIP_H
                )
            if v_flip:
                raw_data = transform_bitpacked(
                    raw_data, src_width, src_height, TransformOperation.FLIP_V
                )
            if rotation == RotationMode.ROTATE_90:
                raw_data = transform_bitpacked(
                    raw_data, src_width, src_height, TransformOperation.ROTATE_90_CW
                )
            elif rotation == RotationMode.ROTATE_180:
                raw_data = transform_bitpacked(
                    raw_data, src_width, src_height, TransformOperation.ROTATE_180
                )
            elif rotation == RotationMode.ROTATE_270:
                raw_data = transform_bitpacked(
                    raw_data, src_width, src_height, TransformOperation.ROTATE_90_CCW
                )
            if invert_colors:
                raw_data = transform_bitpacked(
                    raw_data, src_width, src_height, TransformOperation.INVERT
                )

            self._display_raw(raw_data, mode)
        else:
            # Direct PNG display (must be 128x250)
            # First convert PNG to raw data for capture functionality
            try:
                raw_data = self.convert_image_to_raw(filename)
                self._last_display_data = raw_data
            except Exception:
                # If conversion fails, still try to display
                pass

            filename_bytes = filename.encode("utf-8")
            success = self._lib.display_image_file(filename_bytes, int(mode))
            if not success:
                raise DisplayError(f"Failed to display PNG image: {filename}")

    def _display_raw(self, data: bytes, mode: DisplayMode) -> None:
        """Display raw 1-bit image data."""
        if len(data) != self.ARRAY_SIZE:
            raise DisplayError(f"Data must be exactly {self.ARRAY_SIZE} bytes, got {len(data)}")

        # Store the data for capture functionality
        self._last_display_data = data

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
            self.reacquire_hardware()

        success = self._lib.display_clear()
        if not success:
            raise DisplayError("Failed to clear display")

    def sleep(self) -> None:
        """Put display to sleep for power saving."""
        if self._initialized:
            self._lib.display_sleep()

    def convert_image_to_raw(self, filename: str) -> bytes:
        """
        Convert image file to raw 1-bit data.

        Args:
            filename: Path to image file (must be exactly 128x250 pixels)

        Returns:
            Raw 1-bit packed image data (4000 bytes)

        Raises:
            DisplayError: If conversion fails or path is unsafe
        """
        # Validate path for security
        self._validate_path(filename)

        if not os.path.exists(filename):
            raise DisplayError(f"Image file not found: {filename}")

        # Create output buffer
        output_data = (ctypes.c_ubyte * self.ARRAY_SIZE)()
        filename_bytes = filename.encode("utf-8")

        success = self._lib.convert_image_to_1bit(filename_bytes, output_data)
        if not success:
            raise DisplayError(f"Failed to convert image: {filename}")

        # Convert ctypes array to bytes
        return bytes(output_data)

    def is_initialized(self) -> bool:
        return self._initialized

    def close(self) -> None:
        """Cleanup display resources."""
        if self._initialized:
            self._lib.display_cleanup()
            self._initialized = False

    def release_hardware(self) -> None:
        """
        Release GPIO pins and hardware resources while keeping object alive.
        This allows other processes to use the display.
        """
        if self._initialized:
            self._lib.display_cleanup()
            self._initialized = False
            # Note: Keep library loaded and cache intact

    def reacquire_hardware(
        self,
        max_retries: int = DisplayConstants.MAX_RETRIES,
        retry_delay: float = DisplayConstants.RETRY_DELAY,
    ) -> None:
        """
        Re-initialize hardware when needed after release.
        Will reinitialize configuration and hardware.

        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay in seconds between retries

        Raises:
            DisplayError: If hardware cannot be reacquired
        """
        if self._initialized:
            return

        import time

        for attempt in range(max_retries):
            try:
                # Re-initialize configuration
                config_success = self._lib.display_initialize_config()
                if not config_success and attempt == max_retries - 1:
                    raise DisplayError("Failed to re-initialize display configuration")

                # Re-initialize hardware
                success = self._lib.display_init()
                if success:
                    self._update_dimensions()
                    self._initialized = True
                    return

            except Exception as e:
                if attempt == max_retries - 1:
                    raise DisplayError(
                        f"Failed to reacquire hardware after {max_retries} attempts: {e}"
                    )
                time.sleep(retry_delay)

    def set_firmware(self, firmware_type: str | FirmwareType) -> None:
        """
        Set the default firmware type for the display.

        Args:
            firmware_type: Firmware type string (e.g., "EPD128x250", "EPD240x416")

        Raises:
            DisplayError: If firmware type is invalid or setting fails
        """

        if isinstance(firmware_type, FirmwareType):
            firmware_str = firmware_type.value
        else:
            firmware_str = firmware_type
        firmware_bytes = firmware_str.encode("utf-8")
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
        buffer = ctypes.create_string_buffer(DisplayConstants.FIRMWARE_BUFFER_SIZE)
        success = self._lib.display_get_firmware(buffer, DisplayConstants.FIRMWARE_BUFFER_SIZE)
        if not success:
            raise DisplayError("Failed to get current firmware type")
        return buffer.value.decode("utf-8")

    def initialize_config(self) -> None:
        """
        Initialize the configuration system.
        This loads configuration from environment variables and config files.

        Raises:
            DisplayError: If configuration initialization fails
        """

        success = self._lib.display_initialize_config()
        if not success:
            raise DisplayError("Failed to initialize configuration system")

    def __enter__(self):
        """Context manager entry - acquires hardware."""
        self.reacquire_hardware()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - releases hardware."""
        self.release_hardware()
        return False

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
            return {"entries": 0, "max_size": 0, "total_bytes": 0, "persist_enabled": False}

    def _get_display_dimensions(self) -> tuple[int, int]:
        """Get current display dimensions."""
        if not self._initialized:
            self.initialize()
        return self.WIDTH, self.HEIGHT

    def _convert_image_rust(
        self,
        image_path: str,
        scaling: ScalingMethod = ScalingMethod.LETTERBOX,
        dithering: DitheringMethod = DitheringMethod.FLOYD_STEINBERG,
        rotation: RotationMode = RotationMode.NONE,
        h_flip: bool = False,
        v_flip: bool = False,
        crop_x: int | None = None,
        crop_y: int | None = None,
    ) -> bytes:
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
        filename_bytes = image_path.encode("utf-8")

        # Convert None to -1 for crop coordinates
        crop_x_val = -1 if crop_x is None else crop_x
        crop_y_val = -1 if crop_y is None else crop_y

        # Pass full rotation enum value to Rust library
        success = self._lib.process_image_auto(
            filename_bytes,
            output_data,
            int(scaling),
            int(dithering),
            int(rotation),
            int(h_flip),
            int(v_flip),
            crop_x_val,
            crop_y_val,
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

        filename_bytes = image_path.encode("utf-8")
        return bool(self._lib.is_image_format_supported(filename_bytes))

    def get_supported_formats(self) -> list[str]:
        """
        Get list of supported image formats.

        Returns:
            List of supported file extensions
        """
        buffer = ctypes.create_string_buffer(DisplayConstants.FORMATS_BUFFER_SIZE)
        success = self._lib.get_supported_image_formats(
            buffer, DisplayConstants.FORMATS_BUFFER_SIZE
        )

        if success:
            formats_str = buffer.value.decode("utf-8")
            return formats_str.split(",")

        return ["png"]

    def _convert_image_auto(
        self,
        image_path: str,
        scaling: ScalingMethod = ScalingMethod.LETTERBOX,
        dithering: DitheringMethod = DitheringMethod.FLOYD_STEINBERG,
        rotation: RotationMode = RotationMode.NONE,
        h_flip: bool = False,
        v_flip: bool = False,
        crop_x: int | None = None,
        crop_y: int | None = None,
    ) -> str:
        """
        Convert any image to display-compatible format with caching support.
        Now supports multiple image formats via Rust processing.

        Args:
            image_path: Path to source image file (PNG, JPEG, BMP, TIFF, WebP, etc.)
            scaling: How to scale the image to fit display
            dithering: Dithering method for 1-bit conversion
            rotation: Rotation mode (NONE, ROTATE_90, ROTATE_180, ROTATE_270)
            h_flip: If True, flip image horizontally (left-right mirror)
            v_flip: If True, flip image vertically (top-bottom mirror)
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
                image_path,
                display_width,
                display_height,
                int(scaling),
                int(dithering),
                int(rotation),
                h_flip,
                v_flip,
                crop_x,
                crop_y,
            )
            if cached_path:
                return cached_path

        # Use Rust processing (required)
        # Get raw data from Rust processing
        raw_data = self._convert_image_rust(
            image_path, scaling, dithering, rotation, h_flip, v_flip, crop_x, crop_y
        )

        # Save to temporary PNG file
        temp_fd, temp_path = tempfile.mkstemp(suffix=".png", prefix="eink_auto_")
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
            img_array = img_array[: display_width * display_height]

            # Create PIL image from array
            img = Image.new("L", (display_width, display_height))
            img.putdata(img_array)
            img = img.convert("1")
            img.save(temp_path, "PNG")

            # Store in cache
            if Display._cache_manager:
                Display._cache_manager.put(
                    image_path,
                    display_width,
                    display_height,
                    int(scaling),
                    int(dithering),
                    int(rotation),
                    h_flip,
                    v_flip,
                    crop_x,
                    crop_y,
                    temp_path,
                )

            return temp_path

        except Exception as e:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise DisplayError(f"Failed to save converted image: {e}")

    def _scale_image(
        self,
        img: Image.Image,
        target_width: int,
        target_height: int,
        scaling: ScalingMethod,
        crop_x: int | None = None,
        crop_y: int | None = None,
    ) -> Image.Image:
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
            result = Image.new("RGB", (target_width, target_height), "white")
            paste_x = (target_width - new_width) // 2
            paste_y = (target_height - new_height) // 2
            result.paste(scaled_img, (paste_x, paste_y))

            return result

    def capture_display(self, output_path: str | None = None) -> str:
        """
        Capture the current display content and save it as a PNG file.

        This method saves whatever is currently shown on the e-ink display
        to a PNG file for debugging, sharing, or documentation purposes.

        Args:
            output_path: Path where to save the PNG. If None, saves to
                        /tmp/eink_capture_YYYYMMDD_HHMMSS.png

        Returns:
            Path to the saved PNG file

        Raises:
            DisplayError: If capture fails
        """
        import datetime

        from PIL import Image

        # Generate default filename if not provided
        if output_path is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"/tmp/eink_capture_{timestamp}.png"

        try:
            # Get display dimensions
            width, height = self.get_dimensions()
            bytes_per_row = (width + 7) // 8
            total_bytes = bytes_per_row * height

            # Store the last displayed data if available
            if hasattr(self, "_last_display_data"):
                raw_data = self._last_display_data
            else:
                # If no data stored, create a placeholder
                logger.warning("No display data captured yet. Creating blank image.")
                raw_data = bytes([0x00] * total_bytes)

            # Convert packed bits to image
            img = Image.new("1", (width, height), 0)
            pixels = img.load()

            # Unpack bits from bytes
            for y in range(height):
                for x in range(width):
                    byte_idx = y * bytes_per_row + (x // 8)
                    bit_pos = 7 - (x % 8)  # MSB first
                    if byte_idx < len(raw_data):
                        bit_value = (raw_data[byte_idx] >> bit_pos) & 1
                        pixels[x, y] = bit_value

            # Save as PNG
            img.save(output_path, "PNG")
            logger.info(f"Display captured to: {output_path}")

            return output_path

        except Exception as e:
            raise DisplayError(f"Failed to capture display: {e}")


# Convenience functions for simple usage (following SDK pattern)
def display_image(
    filename: str,
    mode: DisplayMode = DisplayMode.FULL,
    scaling: ScalingMethod = ScalingMethod.LETTERBOX,
    dithering: DitheringMethod = DitheringMethod.FLOYD_STEINBERG,
    rotation: RotationMode = RotationMode.NONE,
    h_flip: bool = False,
    v_flip: bool = False,
    crop_x: int | None = None,
    crop_y: int | None = None,
) -> None:
    """
    Display any supported image format with automatic conversion.
    Supports: PNG, JPEG, GIF, BMP, TIFF, WebP, ICO, PNM, TGA, DDS

    Args:
        filename: Path to image file (any supported format)
        mode: Display refresh mode
        scaling: How to scale the image to fit display
        dithering: Dithering method for 1-bit conversion. Available methods:
            - NONE: Simple threshold (fastest)
            - FLOYD_STEINBERG: High quality error diffusion
            - SIERRA: 3-row error diffusion (better than Floyd-Steinberg)
            - SIERRA_2ROW: 2-row error diffusion (faster than Sierra)
            - SIERRA_LITE: Minimal error diffusion (fast)
            - SIMPLE: Legacy ordered dithering
        rotation: Rotation mode (NONE, ROTATE_90, ROTATE_180, ROTATE_270)
        h_flip: If True, flip image horizontally (left-right mirror)
        v_flip: If True, flip image vertically (top-bottom mirror)
        crop_x: X position for crop when using CROP_CENTER (None = center)
        crop_y: Y position for crop when using CROP_CENTER (None = center)
    """
    with Display() as display:
        display.display_image(
            filename,
            mode,
            scaling,
            dithering,
            rotation,
            h_flip,
            v_flip,
            crop_x=crop_x,
            crop_y=crop_y,
        )


def clear_display() -> None:
    """Convenience function to clear the display."""
    with Display() as display:
        display.clear()


def get_display_info() -> dict:
    """
    Get display information.

    Returns:
        Dictionary with display specs

    Raises:
        DisplayError: If display is not configured
    """
    # Create a temporary display instance to get actual dimensions
    with Display(auto_init=False) as display:
        width, height = display.get_dimensions()
        array_size = (width * height) // 8

    return {
        "width": width,
        "height": height,
        "data_size": array_size,
        "format": "1-bit monochrome",
        "type": "e-ink",
    }


class TransformOperation(IntEnum):
    """Bitpacked image transformation operations."""

    ROTATE_90_CW = 1
    ROTATE_90_CCW = 2
    ROTATE_180 = 3
    FLIP_H = 4
    FLIP_V = 5
    INVERT = 6


def transform_bitpacked(
    src_data: bytes, src_width: int, src_height: int, operation: TransformOperation
) -> bytes:
    """Apply transformation to 1-bit packed bitmap data.

    Args:
        src_data: Source 1-bit packed image data
        src_width: Source width in pixels
        src_height: Source height in pixels
        operation: Transformation to apply

    Returns:
        Transformed 1-bit packed data

    Raises:
        ValueError: If data size doesn't match expected size
    """
    # Validate input
    expected_bytes = (src_width * src_height + 7) // 8
    if len(src_data) < expected_bytes:
        raise ValueError(
            f"Input data too small. Expected {expected_bytes} bytes, got {len(src_data)}"
        )

    # Handle color inversion separately (simple operation)
    if operation == TransformOperation.INVERT:
        return bytes(~byte & 0xFF for byte in src_data)

    # Determine output dimensions
    if operation in (TransformOperation.ROTATE_90_CW, TransformOperation.ROTATE_90_CCW):
        dst_width = src_height
        dst_height = src_width
    else:
        dst_width = src_width
        dst_height = src_height

    dst_bytes = (dst_width * dst_height + 7) // 8
    dst_data = bytearray(dst_bytes)

    # Process each pixel
    for src_y in range(src_height):
        for src_x in range(src_width):
            # Get source bit
            src_bit_idx = src_y * src_width + src_x
            src_byte_idx = src_bit_idx // 8
            src_bit_pos = 7 - (src_bit_idx % 8)
            src_bit = (src_data[src_byte_idx] >> src_bit_pos) & 1

            # Calculate destination coordinates based on operation
            if operation == TransformOperation.ROTATE_90_CW:
                dst_x = src_height - 1 - src_y
                dst_y = src_x
            elif operation == TransformOperation.ROTATE_90_CCW:
                dst_x = src_y
                dst_y = src_width - 1 - src_x
            elif operation == TransformOperation.ROTATE_180:
                dst_x = src_width - 1 - src_x
                dst_y = src_height - 1 - src_y
            elif operation == TransformOperation.FLIP_H:
                dst_x = src_width - 1 - src_x
                dst_y = src_y
            elif operation == TransformOperation.FLIP_V:
                dst_x = src_x
                dst_y = src_height - 1 - src_y
            else:
                raise ValueError(f"Unknown operation: {operation}")

            # Set destination bit
            if operation in (TransformOperation.ROTATE_90_CW, TransformOperation.ROTATE_90_CCW):
                dst_bit_idx = dst_y * dst_width + dst_x
            else:
                dst_bit_idx = dst_y * src_width + dst_x

            dst_byte_idx = dst_bit_idx // 8
            dst_bit_pos = 7 - (dst_bit_idx % 8)

            if src_bit:
                dst_data[dst_byte_idx] |= 1 << dst_bit_pos

    return bytes(dst_data)


# Compatibility aliases for existing code
def rotate_bitpacked_cw_90(src_data: bytes, src_width: int, src_height: int) -> bytes:
    return transform_bitpacked(src_data, src_width, src_height, TransformOperation.ROTATE_90_CW)


def rotate_bitpacked_ccw_90(src_data: bytes, src_width: int, src_height: int) -> bytes:
    return transform_bitpacked(src_data, src_width, src_height, TransformOperation.ROTATE_90_CCW)


def rotate_bitpacked_180(src_data: bytes, src_width: int, src_height: int) -> bytes:
    return transform_bitpacked(src_data, src_width, src_height, TransformOperation.ROTATE_180)


def h_flip_bitpacked(src_data: bytes, src_width: int, src_height: int) -> bytes:
    return transform_bitpacked(src_data, src_width, src_height, TransformOperation.FLIP_H)


def v_flip_bitpacked(src_data: bytes, src_width: int, src_height: int) -> bytes:
    return transform_bitpacked(src_data, src_width, src_height, TransformOperation.FLIP_V)


def invert_bitpacked_colors(src_data: bytes) -> bytes:
    return transform_bitpacked(src_data, 0, 0, TransformOperation.INVERT)


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
