#!/usr/bin/env python3
"""
Interactive LED Demo and Test Suite (Static Control Only)

This demo showcases basic LED functionality in an interactive way.
Press Enter to continue between each demo section.
Run as: python led_interactive_demo.py

Features demonstrated:
- LED discovery and initialization
- RGB color control (static only)
- Brightness control
- Multi-LED static control
- Convenience methods (static only)
- Error handling
"""

import time
import sys
import signal
from led import LEDError, create_led_with_sudo


class InteractiveLEDDemo:
    """Interactive LED demonstration class for static control only."""

    def __init__(self):
        """Initialize the demo."""
        self.led = None
        self.available_leds = []

    def wait_for_enter(self, message="Press Enter to continue..."):
        """Wait for user to press Enter."""
        try:
            input(f"\n💡 {message}")
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def print_section(self, title, description=""):
        """Print a formatted section header."""
        print(f"\n{'=' * 60}")
        print(f"🎯 {title}")
        print(f"{'=' * 60}")
        if description:
            print(f"📝 {description}")

    def demo_initialization(self):
        """Demo 1: LED initialization and discovery."""
        self.print_section(
            "Demo 1: LED Initialization", "Discovering available LEDs and setting up sudo mode"
        )

        print("🔧 Initializing LED module with sudo mode...")
        self.led = create_led_with_sudo()
        print("✅ LED module initialized successfully!")

        self.available_leds = self.led.get_available_leds()
        print(f"🔍 Discovered LEDs: {self.available_leds}")
        print(f"📊 Total LEDs found: {len(self.available_leds)}")

        if not self.available_leds:
            raise LEDError("❌ No LEDs found! Check if the SAM driver is loaded.")

        self.wait_for_enter("Ready to test RGB colors?")

    def demo_rgb_colors(self):
        """Demo 2: RGB color control."""
        self.print_section(
            "Demo 2: RGB Color Control", "Testing primary and secondary colors on LED 0"
        )

        led_id = self.available_leds[0]
        print(f"🎨 Testing RGB colors on LED {led_id}...")

        colors = [
            (255, 0, 0, "🔴 Red"),
            (0, 255, 0, "🟢 Green"),
            (0, 0, 255, "🔵 Blue"),
            (255, 255, 0, "🟡 Yellow"),
            (255, 0, 255, "🟣 Magenta"),
            (0, 255, 255, "🩵 Cyan"),
            (255, 128, 0, "🟠 Orange"),
            (255, 255, 255, "⚪ White"),
            (128, 64, 0, "🤎 Brown"),
            (0, 128, 64, "🟢 Forest Green"),
        ]

        for red, green, blue, name in colors:
            print(f"Setting {name} - RGB({red}, {green}, {blue})")
            self.led.set_rgb_color(led_id, red, green, blue)
            self.led.set_brightness(led_id, 200)

            # Verify the color was set
            current = self.led.get_rgb_color(led_id)
            print(f"  ✓ Verified: RGB{current}")
            time.sleep(0.8)

        self.wait_for_enter("Ready to test brightness control?")

    def demo_brightness_control(self):
        """Demo 3: Brightness control."""
        self.print_section(
            "Demo 3: Brightness Control",
            "Demonstrating brightness levels while preserving color ratios",
        )

        led_id = self.available_leds[0]
        print(f"💡 Testing brightness control on LED {led_id}...")

        # Set a nice purple color
        self.led.set_rgb_color(led_id, 128, 0, 255)
        print("🟣 Set base color: Purple RGB(128, 0, 255)")

        brightness_levels = [
            (255, "🌟 Maximum (100%)"),
            (192, "☀️ High (75%)"),
            (128, "🌤️ Medium (50%)"),
            (64, "🌙 Low (25%)"),
            (16, "🌑 Very Low (6%)"),
            (0, "⚫ Off (0%)"),
            (128, "🌤️ Back to Medium"),
        ]

        for brightness, description in brightness_levels:
            print(f"Setting brightness: {description} - {brightness}/255")
            self.led.set_brightness(led_id, brightness)

            # Verify brightness was set
            current = self.led.get_brightness(led_id)
            print(f"  ✓ Verified: {current}/255")
            time.sleep(1.2)

        self.wait_for_enter("Ready to test multi-LED static control?")

    def demo_multi_led_static(self):
        """Demo 4: Multi-LED static control."""
        self.print_section(
            "Demo 4: Multi-LED Static Control", "Setting different static colors on multiple LEDs"
        )

        if len(self.available_leds) == 1:
            print("ℹ️ Single LED system - demonstrating color changes on one LED")
            led_id = self.available_leds[0]

            colors = [
                (255, 0, 0, "🔴 Red"),
                (0, 255, 0, "🟢 Green"),
                (0, 0, 255, "🔵 Blue"),
                (255, 255, 0, "🟡 Yellow"),
                (255, 0, 255, "🟣 Magenta"),
            ]

            for red, green, blue, name in colors:
                print(f"LED {led_id}: {name}")
                self.led.static_led(led_id, red, green, blue)
                self.led.set_brightness(led_id, 150)
                time.sleep(1.5)

        else:
            print(f"🎨 Setting different colors on {len(self.available_leds)} LEDs...")

            # Define colors for multiple LEDs
            colors = [
                (255, 0, 0, "🔴 Red"),  # LED 0
                (0, 255, 0, "🟢 Green"),  # LED 1
                (0, 0, 255, "🔵 Blue"),  # LED 2
                (255, 255, 0, "🟡 Yellow"),  # LED 3
                (255, 0, 255, "🟣 Magenta"),  # LED 4
                (0, 255, 255, "🩵 Cyan"),  # LED 5
                (255, 128, 0, "🟠 Orange"),  # LED 6
                (128, 0, 128, "🟣 Purple"),  # LED 7+
            ]

            for i, led_id in enumerate(self.available_leds):
                if i < len(colors):
                    r, g, b, name = colors[i]
                else:
                    # Cycle through colors for additional LEDs
                    r, g, b, name = colors[i % len(colors)]

                print(f"LED {led_id}: {name} - RGB({r}, {g}, {b})")
                self.led.set_rgb_color(led_id, r, g, b)
                self.led.set_brightness(led_id, 150)
                time.sleep(0.3)

            print(f"\n✨ All {len(self.available_leds)} LEDs now showing different static colors!")
            time.sleep(3)

        self.wait_for_enter("Ready to test convenience methods?")

    def demo_convenience_methods(self):
        """Demo 5: Convenience methods."""
        self.print_section(
            "Demo 5: Convenience Methods", "Testing bulk operations and helper functions"
        )

        if len(self.available_leds) > 1:
            print(f"🎯 Testing bulk operations on {len(self.available_leds)} LEDs...")

            print("🌟 Using set_color_all() - All LEDs to white")
            self.led.set_color_all(255, 255, 255)
            time.sleep(1.5)

            print("🔅 Using set_brightness_all() - All LEDs to 30%")
            self.led.set_brightness_all(76)
            time.sleep(1.5)

            print("🎨 Setting different colors individually...")
            colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
            for i, led_id in enumerate(self.available_leds[:4]):
                if i < len(colors):
                    r, g, b = colors[i]
                    self.led.set_rgb_color(led_id, r, g, b)
                    print(f"  LED {led_id}: RGB({r}, {g}, {b})")
            time.sleep(2)

            print("⚫ Using turn_off_all() - All LEDs off")
            self.led.turn_off_all()
            time.sleep(1)
        else:
            print("ℹ️ Single LED system - testing individual convenience methods...")
            led_id = self.available_leds[0]

            print(f"🔸 static_led() - Static purple on LED {led_id}")
            self.led.static_led(led_id, 128, 0, 255)
            time.sleep(1.5)

            print(f"⚫ turn_off() - Turn off LED {led_id}")
            self.led.turn_off(led_id)
            time.sleep(1)

        self.wait_for_enter("Ready to test error handling?")

    def demo_error_handling(self):
        """Demo 6: Error handling."""
        self.print_section("Demo 6: Error Handling", "Testing input validation and error messages")

        valid_led = self.available_leds[0]
        print("🧪 Testing error handling and validation...")

        test_cases = [
            ("Invalid LED ID", lambda: self.led.set_rgb_color(999, 255, 0, 0)),
            ("Invalid RGB value", lambda: self.led.set_rgb_color(valid_led, 300, 0, 0)),
            ("Invalid brightness", lambda: self.led.set_brightness(valid_led, 300)),
            ("Disabled animation mode", lambda: self.led.set_animation_mode(valid_led, "blink")),
            ("Disabled trigger", lambda: self.led.set_trigger(valid_led, "heartbeat-rgb")),
            ("Disabled blink method", lambda: self.led.blink_led(valid_led, 255, 0, 0)),
            ("Disabled fade method", lambda: self.led.fade_led(valid_led, 0, 255, 0)),
            ("Disabled rainbow method", lambda: self.led.rainbow_led(valid_led)),
        ]

        for description, test_func in test_cases:
            try:
                test_func()
                print(f"❌ {description}: Should have failed!")
            except (LEDError, NotImplementedError) as e:
                print(f"✅ {description}: Correctly caught - {str(e)[:60]}...")
            except Exception as e:
                print(f"⚠️ {description}: Unexpected error - {e}")

        self.wait_for_enter("Ready to test sudo mode switching?")

    def demo_sudo_mode(self):
        """Demo 7: Sudo mode switching."""
        self.print_section(
            "Demo 7: Sudo Mode Management", "Testing sudo mode switching functionality"
        )

        print("🔐 Testing sudo mode switching...")

        original_mode = self.led.use_sudo
        print(f"📊 Current sudo mode: {original_mode}")

        # Switch mode
        new_mode = not original_mode
        print(f"🔄 Switching to sudo mode: {new_mode}")
        self.led.set_sudo_mode(new_mode)

        if self.led.use_sudo == new_mode:
            print("✅ Sudo mode successfully changed")
        else:
            print("❌ Failed to change sudo mode")

        # Switch back
        print(f"🔄 Restoring original sudo mode: {original_mode}")
        self.led.set_sudo_mode(original_mode)
        print(f"📊 Final sudo mode: {self.led.use_sudo}")

        self.wait_for_enter("Ready for the final cleanup demo?")

    def demo_cleanup(self):
        """Demo 8: Cleanup and summary."""
        self.print_section("Demo 8: Cleanup & Summary", "Proper cleanup and demonstration summary")

        print("🧹 Performing comprehensive cleanup...")

        # Turn off all LEDs
        print(f"⚫ Turning off all {len(self.available_leds)} LEDs...")
        self.led.turn_off_all()

        print("\n📊 Demo Summary:")
        print(f"  ✅ LEDs tested: {len(self.available_leds)}")
        print("  ✅ RGB colors: Primary and secondary colors")
        print("  ✅ Brightness: Multiple levels (0-255)")
        print("  ✅ Static control: Individual and bulk operations")
        print("  ✅ Convenience: Helper functions")
        print("  ✅ Error handling: Input validation")
        print("  ✅ Sudo mode: Permission management")
        print("  ✅ Cleanup: Proper resource cleanup")
        print("  ⚠️ Animations/Triggers: Disabled (static control only)")

        print("\n🎉 All static LED functionality demonstrated successfully!")

    def run_full_demo(self):
        """Run the complete interactive demo."""
        print("🌈 Interactive LED Demo and Test Suite (Static Control)")
        print("=" * 60)
        print("📝 This demo walks you through static LED functionality only")
        print("💡 Press Enter between sections to continue")
        print("🛑 Press Ctrl+C anytime to exit safely")
        print("⚠️ Note: Animations and triggers have been disabled")

        try:
            self.wait_for_enter("Ready to start the LED demo?")

            # Run all demo sections
            self.demo_initialization()
            self.demo_rgb_colors()
            self.demo_brightness_control()
            self.demo_multi_led_static()
            self.demo_convenience_methods()
            self.demo_error_handling()
            self.demo_sudo_mode()
            self.demo_cleanup()

            print("\n🎊 Demo completed successfully!")
            print("Thank you for trying the LED module (static control)!")

        except KeyboardInterrupt:
            print("\n🛑 Demo interrupted by user")
            self.cleanup_on_exit()
        except LEDError as e:
            print(f"\n❌ LED Error: {e}")
            if "Permission denied" in str(e):
                print("💡 Tip: Run with proper sudo permissions")
            self.cleanup_on_exit()
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            self.cleanup_on_exit()

    def cleanup_on_exit(self):
        """Cleanup when exiting unexpectedly."""
        if self.led and self.available_leds:
            print("🧹 Emergency cleanup...")
            try:
                self.led.turn_off_all()
                print("✅ Cleanup completed")
            except Exception:
                print("⚠️ Cleanup failed - LEDs may still be active")


def main():
    """Main function."""

    # Set up signal handler for clean exit
    def signal_handler(sig, frame):
        print("\n🛑 Received exit signal...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the demo
    demo = InteractiveLEDDemo()
    demo.run_full_demo()

    return 0


if __name__ == "__main__":
    sys.exit(main())
