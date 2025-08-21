"""Hardware interface service for e-ink display."""

import socket
from pathlib import Path
from typing import Optional

from PIL import Image

from .debug import debug, debug_manager, error, info, log_call, timed_operation, warning


class HardwareService:
    """Service for interfacing with e-ink hardware."""

    def __init__(self):
        """Initialize hardware service."""
        self.display = None
        self.firmware = None
        self.width = 250
        self.height = 128
        info("Initializing HardwareService")
        self._init_hardware()

    def _init_hardware(self):
        """Initialize e-ink hardware if available."""
        try:
            from distiller_cm5_sdk.hardware.eink import (
                Display,
                get_default_firmware,
                get_display_info,
            )

            self.display = Display()
            self.firmware = get_default_firmware()

            # Get actual display dimensions
            display_info = get_display_info()
            if display_info and "width" in display_info and "height" in display_info:
                # The hardware reports dimensions in portrait mode (128x250)
                # but we use it in landscape mode (250x128)
                # Check firmware type to determine if we need to swap
                if self.firmware and "128x250" in str(self.firmware):
                    # Swap dimensions for landscape orientation
                    self.width = display_info["height"]
                    self.height = display_info["width"]
                    info(
                        f"Hardware detected: {display_info['width']}x{display_info['height']} (portrait), using {self.width}x{self.height} (landscape), firmware: {self.firmware}"
                    )
                else:
                    self.width = display_info["width"]
                    self.height = display_info["height"]
                    info(
                        f"Hardware detected: {self.width}x{self.height}, firmware: {self.firmware}"
                    )
            else:
                warning("Could not get display info, using defaults")

        except Exception as e:
            error(f"Hardware initialization failed: {e}")
            debug_manager.log_error("hardware_init", e)
            self.display = None

    def is_available(self) -> bool:
        """Check if hardware is available."""
        return self.display is not None

    def get_dimensions(self) -> tuple[int, int]:
        """Get display dimensions."""
        return self.width, self.height

    def get_firmware(self) -> str | None:
        """Get firmware type."""
        return self.firmware

    @timed_operation("display_image")
    @log_call
    def display_image(
        self,
        image: Image.Image,
        partial: bool = False,
        rotate: bool = False,
        flip_h: bool = False,
        flip_v: bool = False,
    ) -> bool:
        """Display an image on the e-ink screen."""
        if not self.display:
            warning("Display not available")
            return False

        try:
            # Ensure image is correct size
            if image.size != (self.width, self.height):
                debug(f"Resizing image from {image.size} to ({self.width}, {self.height})")
                image = image.resize((self.width, self.height))

            # Convert to grayscale if needed
            if image.mode != "L":
                image = image.convert("L")
            
            # No color inversion needed - renderer provides correct colors for e-ink
            # 0 = black ink, 255 = white/no ink
            
            # CRITICAL: Rotate from landscape (250x128) to portrait (128x250) for hardware
            # The UI works in landscape but hardware expects portrait orientation
            debug(f"Rotating image from landscape {image.size} to portrait for hardware")
            image = image.transpose(Image.Transpose.ROTATE_270)  # Rotate 270° (or -90°) to convert landscape to portrait
            debug(f"Image rotated to {image.size} for hardware display")
            
            # Apply horizontal flip to correct mirror issue
            debug("Applying horizontal flip to correct display mirroring")
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

            # Apply additional transformations if requested
            if rotate:
                image = image.rotate(90)
            if flip_h:
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if flip_v:
                image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

            # Save to temporary file with proper permissions
            import os
            import tempfile

            # Create temp directory if it doesn't exist
            temp_dir = Path("/tmp/eink_composer")
            temp_dir.mkdir(mode=0o777, exist_ok=True)

            # Create temp file with world-writable permissions
            with tempfile.NamedTemporaryFile(
                dir=temp_dir, suffix=".png", delete=False, mode="wb"
            ) as temp_file:
                temp_path = Path(temp_file.name)
                image.save(temp_file, format="PNG")

            # Ensure file is readable by the distiller user/group
            os.chmod(temp_path, 0o666)

            # Display on hardware
            from distiller_cm5_sdk.hardware.eink import DisplayMode, display_image

            mode = DisplayMode.PARTIAL if partial else DisplayMode.FULL
            debug(
                f"Displaying image: {temp_path}, mode: {mode.name}, rotate: {rotate}, flip_h: {flip_h}, flip_v: {flip_v}"
            )
            display_image(str(temp_path), mode=mode)
            info("Successfully displayed image on hardware")

            # Clean up
            temp_path.unlink(missing_ok=True)

            return True

        except Exception as e:
            error(f"Display error: {e}")
            debug_manager.log_error(
                "display_image",
                e,
                {"image_size": image.size if image else None, "partial": partial, "rotate": rotate},
            )
            return False

    @timed_operation("clear_display")
    @log_call
    def clear(self, color: int = 255) -> bool:
        """Clear the display."""
        if not self.display:
            warning("Display not available for clear")
            return False

        try:
            from distiller_cm5_sdk.hardware.eink import clear_display

            debug("Clearing display (always clears to white)")
            # Note: clear_display() doesn't accept arguments, it always clears to white
            clear_display()
            info("Display cleared successfully")
            return True

        except Exception as e:
            error(f"Clear error: {e}")
            debug_manager.log_error("clear_display", e, {"color": color})
            return False

    def get_ip_address(self) -> str:
        """Get device IP address."""
        try:
            # Create a socket to determine IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def get_status(self) -> dict:
        """Get hardware status."""
        status = {
            "available": self.is_available(),
            "firmware": self.firmware,
            "width": self.width,
            "height": self.height,
            "ip_address": self.get_ip_address(),
        }
        debug(f"Hardware status: {status}")
        return status
