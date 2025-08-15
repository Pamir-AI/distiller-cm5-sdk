import subprocess
from pathlib import Path


class LEDError(Exception):
    """Custom exception for LED-related errors."""
    pass


class LED:
    """
    SDK interface for RGB LED control via sysfs.

    This class provides comprehensive RGB LED control with support for:
    - Multiple LEDs (led0, led1, led2, etc.)
    - RGB color control (0-255 per component)
    - Animation modes (static, blink, fade, rainbow)
    - LED triggers (heartbeat-rgb, breathing-rgb, rainbow-rgb)
    - Brightness control (0-255)
    - Timing control for animations (100-1600ms)

    Note: Most operations require root privileges. Use sudo or set use_sudo=True.
    """

    # Note: Animation modes and triggers have been removed - only static control available

    def __init__(self, base_path: str = "/sys/class/leds", use_sudo: bool = False):
        """
        Initialize the LED module interface.

        Args:
            base_path: Base path for LED sysfs interface (default: /sys/class/leds)
            use_sudo: Whether to use sudo for write operations (default: False)

        Raises:
            LEDError: If the sysfs interface is not available or accessible
        """
        self.base_path = Path(base_path)
        self.use_sudo = use_sudo

        # Check if sysfs interface exists
        if not self.base_path.exists():
            raise LEDError(f"LED sysfs interface not found at {base_path}")

        # Discover available LEDs
        self.available_leds = self._discover_leds()

        if not self.available_leds:
            raise LEDError("No compatible LEDs found (pamir:led* pattern)")

    def _discover_leds(self) -> list[int]:
        """
        Discover available LEDs by scanning for pamir:led* directories.

        Returns:
            List of LED numbers (e.g., [0, 1, 2] for led0, led1, led2)
        """
        leds = []

        try:
            for item in self.base_path.iterdir():
                if item.is_dir() and item.name.startswith("pamir:led"):
                    try:
                        led_num = int(item.name.replace("pamir:led", ""))
                        leds.append(led_num)
                    except ValueError:
                        continue
        except (OSError, PermissionError):
            pass

        return sorted(leds)

    def _get_led_path(self, led_id: int) -> Path:
        """
        Get the sysfs path for a specific LED.

        Args:
            led_id: LED number (0, 1, 2, etc.)

        Returns:
            Path to the LED's sysfs directory

        Raises:
            LEDError: If LED ID is not available
        """
        if led_id not in self.available_leds:
            raise LEDError(f"LED {led_id} not available. Available LEDs: {self.available_leds}")

        return self.base_path / f"pamir:led{led_id}"

    def _write_sysfs_file(self, file_path: Path, value: str) -> None:
        """
        Write a value to a sysfs file.

        Args:
            file_path: Path to sysfs file
            value: Value to write

        Raises:
            LEDError: If writing fails
        """
        if self.use_sudo:
            try:
                # Use subprocess with sudo to write the value
                cmd = ["sudo", "tee", str(file_path)]
                subprocess.run(
                    cmd,
                    input=str(value),
                    text=True,
                    capture_output=True,
                    check=True
                )
            except subprocess.CalledProcessError as e:
                raise LEDError(f"Failed to write '{value}' to {file_path} using sudo: {e}")
            except FileNotFoundError:
                raise LEDError("sudo command not found. Please install sudo or run as root.")
        else:
            try:
                with open(file_path, 'w') as f:
                    f.write(str(value))
                    f.flush()
            except PermissionError as e:
                raise LEDError(
                    f"Permission denied writing to {file_path}. "
                    f"Try running with sudo or initialize LED(use_sudo=True). "
                    f"Original error: {e}"
                )
            except OSError as e:
                raise LEDError(f"Failed to write '{value}' to {file_path}: {e}")

    def _read_sysfs_file(self, file_path: Path) -> str:
        """
        Read a value from a sysfs file.

        Args:
            file_path: Path to sysfs file

        Returns:
            Content of the file (stripped)

        Raises:
            LEDError: If reading fails
        """
        try:
            with open(file_path) as f:
                return f.read().strip()
        except (OSError, PermissionError) as e:
            raise LEDError(f"Failed to read from {file_path}: {e}")

    def set_sudo_mode(self, use_sudo: bool) -> None:
        """
        Enable or disable sudo mode for write operations.

        Args:
            use_sudo: Whether to use sudo for write operations
        """
        self.use_sudo = use_sudo

    def get_available_leds(self) -> list[int]:
        """
        Get list of available LED IDs.

        Returns:
            List of available LED numbers
        """
        return self.available_leds.copy()

    def set_rgb_color(self, led_id: int, red: int, green: int, blue: int) -> None:
        """
        Set RGB color for a specific LED.

        Args:
            led_id: LED number (0, 1, 2, etc.)
            red: Red component (0-255)
            green: Green component (0-255)
            blue: Blue component (0-255)

        Raises:
            LEDError: If LED ID is invalid or values are out of range
        """
        # Validate color values
        for component, value in [("red", red), ("green", green), ("blue", blue)]:
            if not 0 <= value <= 255:
                raise LEDError(f"{component.capitalize()} value {value} out of range (0-255)")

        led_path = self._get_led_path(led_id)

        # Set RGB components
        self._write_sysfs_file(led_path / "red", str(red))
        self._write_sysfs_file(led_path / "green", str(green))
        self._write_sysfs_file(led_path / "blue", str(blue))

    def get_rgb_color(self, led_id: int) -> tuple[int, int, int]:
        """
        Get current RGB color for a specific LED.

        Args:
            led_id: LED number (0, 1, 2, etc.)

        Returns:
            Tuple of (red, green, blue) values (0-255)

        Raises:
            LEDError: If LED ID is invalid or reading fails
        """
        led_path = self._get_led_path(led_id)

        try:
            red = int(self._read_sysfs_file(led_path / "red"))
            green = int(self._read_sysfs_file(led_path / "green"))
            blue = int(self._read_sysfs_file(led_path / "blue"))
            return (red, green, blue)
        except ValueError as e:
            raise LEDError(f"Failed to parse RGB values for LED {led_id}: {e}")

    def set_animation_mode(self, led_id: int, mode: str, timing: int | None = None) -> None:
        """
        Set animation mode for a specific LED.

        NOTE: Animation modes have been disabled in this version.
        Only static color control is available.

        Raises:
            NotImplementedError: Animation modes are not implemented
        """
        raise NotImplementedError("Animation modes have been removed. Use set_rgb_color() for static control only.")

    def get_animation_mode(self, led_id: int) -> tuple[str, int]:
        """
        Get current animation mode and timing for a specific LED.

        NOTE: Animation modes have been disabled in this version.

        Raises:
            NotImplementedError: Animation modes are not implemented
        """
        raise NotImplementedError("Animation modes have been removed. Use get_rgb_color() and get_brightness() instead.")

    def set_trigger(self, led_id: int, trigger: str) -> None:
        """
        Set LED trigger for a specific LED.

        NOTE: LED triggers have been disabled in this version.
        Only static color control is available.

        Raises:
            NotImplementedError: LED triggers are not implemented
        """
        raise NotImplementedError("LED triggers have been removed. Use set_rgb_color() for static control only.")

    def get_trigger(self, led_id: int) -> str:
        """
        Get current trigger for a specific LED.

        NOTE: LED triggers have been disabled in this version.

        Raises:
            NotImplementedError: LED triggers are not implemented
        """
        raise NotImplementedError("LED triggers have been removed. Use get_rgb_color() and get_brightness() instead.")

    def get_available_triggers(self, led_id: int) -> list[str]:
        """
        Get list of available triggers for a specific LED.

        NOTE: LED triggers have been disabled in this version.

        Raises:
            NotImplementedError: LED triggers are not implemented
        """
        raise NotImplementedError("LED triggers have been removed. Only static color control is available.")

    def set_brightness(self, led_id: int, brightness: int) -> None:
        """
        Set overall brightness for a specific LED.

        Args:
            led_id: LED number (0, 1, 2, etc.)
            brightness: Brightness value (0-255)

        Raises:
            LEDError: If LED ID is invalid or brightness is out of range
        """
        if not 0 <= brightness <= 255:
            raise LEDError(f"Brightness {brightness} out of range (0-255)")

        led_path = self._get_led_path(led_id)
        self._write_sysfs_file(led_path / "brightness", str(brightness))

    def get_brightness(self, led_id: int) -> int:
        """
        Get current brightness for a specific LED.

        Args:
            led_id: LED number (0, 1, 2, etc.)

        Returns:
            Current brightness value (0-255)

        Raises:
            LEDError: If LED ID is invalid or reading fails
        """
        led_path = self._get_led_path(led_id)

        try:
            return int(self._read_sysfs_file(led_path / "brightness"))
        except ValueError as e:
            raise LEDError(f"Failed to parse brightness for LED {led_id}: {e}")

    # Convenience methods for common operations

    def turn_off(self, led_id: int) -> None:
        """
        Turn off a specific LED.

        Args:
            led_id: LED number (0, 1, 2, etc.)
        """
        self.set_rgb_color(led_id, 0, 0, 0)
        self.set_brightness(led_id, 0)

    def turn_off_all(self) -> None:
        """Turn off all available LEDs."""
        for led_id in self.available_leds:
            self.turn_off(led_id)

    def set_color_all(self, red: int, green: int, blue: int) -> None:
        """
        Set the same RGB color for all available LEDs.

        Args:
            red: Red component (0-255)
            green: Green component (0-255)
            blue: Blue component (0-255)
        """
        for led_id in self.available_leds:
            self.set_rgb_color(led_id, red, green, blue)

    def set_brightness_all(self, brightness: int) -> None:
        """
        Set the same brightness for all available LEDs.

        Args:
            brightness: Brightness value (0-255)
        """
        for led_id in self.available_leds:
            self.set_brightness(led_id, brightness)

    def blink_led(self, led_id: int, red: int, green: int, blue: int,
                  timing: int = 500) -> None:
        """
        Set a LED to blink with specified color.

        NOTE: Animation modes have been disabled in this version.

        Raises:
            NotImplementedError: Animation modes are not implemented
        """
        raise NotImplementedError("Blinking animation has been removed. Use set_rgb_color() for static control only.")

    def fade_led(self, led_id: int, red: int, green: int, blue: int,
                 timing: int = 1000) -> None:
        """
        Set a LED to fade with specified color.

        NOTE: Animation modes have been disabled in this version.

        Raises:
            NotImplementedError: Animation modes are not implemented
        """
        raise NotImplementedError("Fading animation has been removed. Use set_rgb_color() for static control only.")

    def rainbow_led(self, led_id: int, timing: int = 1000) -> None:
        """
        Set a LED to rainbow cycle mode.

        NOTE: Animation modes have been disabled in this version.

        Raises:
            NotImplementedError: Animation modes are not implemented
        """
        raise NotImplementedError("Rainbow animation has been removed. Use set_rgb_color() for static control only.")

    def static_led(self, led_id: int, red: int, green: int, blue: int) -> None:
        """
        Set a LED to static color.

        Args:
            led_id: LED number (0, 1, 2, etc.)
            red: Red component (0-255)
            green: Green component (0-255)
            blue: Blue component (0-255)
        """
        self.set_rgb_color(led_id, red, green, blue)

    # Legacy compatibility methods (matching old interface)

    def connect(self) -> bool:
        """
        Legacy compatibility method.

        Returns:
            bool: Always True (sysfs interface doesn't require connection)
        """
        return True

    def disconnect(self) -> None:
        """
        Legacy compatibility method.
        """
        pass

    def set_led_color(self, r: int, g: int, b: int, brightness: float = 0.5,
                      delay: float = 0.0, led_id: int = 0) -> bool:
        """
        Legacy compatibility method for setting LED color.

        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
            brightness: LED brightness (0.0-1.0)
            delay: Ignored (for compatibility)
            led_id: LED number (default: 0)

        Returns:
            bool: True if successful
        """
        try:
            # Convert brightness from 0.0-1.0 to 0-255
            brightness_int = int(brightness * 255)

            self.set_rgb_color(led_id, r, g, b)
            self.set_brightness(led_id, brightness_int)

            # Note: delay parameter is ignored in this static-only version

            return True
        except LEDError:
            return False


# Convenience function for quick LED access with sudo
def create_led_with_sudo() -> LED:
    """
    Create an LED instance with sudo enabled.

    Returns:
        LED instance configured to use sudo for write operations
    """
    return LED(use_sudo=True)

