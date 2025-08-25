#!/usr/bin/env python3
"""
Hardware Integration Tests for SAM LED Module

This test suite validates LED hardware functionality via sysfs interface.

Hardware Requirements:
- Pamir AI SAM module with kernel driver loaded
- One or more RGB LEDs connected (pamir:led0, pamir:led1, etc.)
- Root/sudo privileges for sysfs writes
- /sys/class/leds/pamir:led* interfaces available

Activate the SDK venv before running:
source /path/to/distiller_cm5_sdk/.venv/bin/activate

Run with: sudo uv run pytest led_test.py -v
Or Run with: sudo python -m pytest led_test.py -v
Or: sudo python led_test.py
"""

import os
import sys
import time
import unittest
import argparse
from pathlib import Path

# Import the LED module
from distiller_cm5_sdk.hardware.sam.led import LED, LEDError


class HardwareTestBase(unittest.TestCase):
    """Base class for hardware tests with common setup and utilities."""

    @classmethod
    def setUpClass(cls):
        """One-time setup for all hardware tests."""
        # Check if running with sufficient privileges
        if os.geteuid() != 0:
            print("WARNING: Tests require root privileges. Some tests may fail.")
            print("Run with: sudo python led_test.py")

        # Check if hardware is available
        cls.sysfs_base = Path("/sys/class/leds")
        if not cls.sysfs_base.exists():
            raise unittest.SkipTest("LED sysfs interface not available - hardware not present")

        # Check for pamir LEDs (hardware supports LEDs 0-6)
        cls.available_leds = []
        for led_path in cls.sysfs_base.iterdir():
            if led_path.name.startswith("pamir:led"):
                try:
                    led_num = int(led_path.name.replace("pamir:led", ""))
                    # Hardware only supports LEDs 0-6
                    if 0 <= led_num <= 6:
                        cls.available_leds.append(led_num)
                except ValueError:
                    continue

        if not cls.available_leds:
            raise unittest.SkipTest("No Pamir LEDs found - hardware not present")

        cls.available_leds.sort()
        print(f"\n[Hardware Test] Found {len(cls.available_leds)} LED(s): {cls.available_leds}")
        print(f"[Hardware Test] Testing with actual hardware at {cls.sysfs_base}")

    def setUp(self):
        """Set up each test with a fresh LED instance."""
        try:
            self.led = LED(use_sudo=(os.geteuid() != 0))
            # Reset all LEDs to a known state
            for led_id in self.led.available_leds:
                self.led.turn_off(led_id)
                time.sleep(0.2)  # Quick delay for hardware to process
        except LEDError as e:
            self.skipTest(f"Failed to initialize LED module: {e}")

    def tearDown(self):
        """Clean up after each test."""
        # Turn off all LEDs
        if hasattr(self, "led"):
            try:
                self.led.turn_off_all()
            except Exception:
                pass

    def measure_time(self, func, *args, **kwargs):
        """Measure execution time of a function."""
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        return result, elapsed * 1000  # Return result and time in ms


class TestHardwareDetection(HardwareTestBase):
    """Test hardware detection and initialization."""

    def test_hardware_present(self):
        """Verify LED hardware is detected."""
        self.assertTrue(len(self.available_leds) > 0, "No LED hardware detected")
        print(f"  ✓ Detected {len(self.available_leds)} LED(s)")

    def test_sysfs_attributes_present(self):
        """Verify all required sysfs attributes exist."""
        required_attrs = ["red", "green", "blue", "brightness", "mode", "timing", "trigger"]

        for led_id in self.available_leds:
            led_path = self.sysfs_base / f"pamir:led{led_id}"
            self.assertTrue(led_path.exists(), f"LED {led_id} path missing")

            for attr in required_attrs:
                attr_path = led_path / attr
                self.assertTrue(attr_path.exists(), f"LED {led_id} missing attribute: {attr}")

            print(f"  ✓ LED {led_id} has all required attributes")

    def test_led_discovery(self):
        """Test LED discovery matches actual hardware."""
        discovered = self.led.get_available_leds()
        self.assertEqual(
            set(discovered), set(self.available_leds), "LED discovery mismatch with actual hardware"
        )
        print(f"  ✓ LED discovery correct: {discovered}")

    def test_read_initial_state(self):
        """Test reading initial hardware state."""
        for led_id in self.led.available_leds[:1]:  # Test first LED
            # Read RGB values
            r, g, b = self.led.get_rgb_color(led_id)
            self.assertIsInstance(r, int)
            self.assertIsInstance(g, int)
            self.assertIsInstance(b, int)
            print(f"  ✓ LED {led_id} initial RGB: ({r}, {g}, {b})")

            # Read brightness
            brightness = self.led.get_brightness(led_id)
            self.assertIsInstance(brightness, int)
            print(f"  ✓ LED {led_id} initial brightness: {brightness}")

            # Read mode and timing
            mode, timing = self.led.get_animation_mode(led_id)
            self.assertIsInstance(mode, str)
            self.assertIsInstance(timing, int)
            print(f"  ✓ LED {led_id} initial mode: {mode}, timing: {timing}ms")


class TestRGBHardwareControl(HardwareTestBase):
    """Test RGB color control on actual hardware."""

    def test_set_rgb_basic_colors(self):
        """Test setting basic RGB colors on hardware."""
        test_colors = [
            (255, 0, 0, "Red"),
            (0, 255, 0, "Green"),
            (0, 0, 255, "Blue"),
            (255, 255, 0, "Yellow"),
            (255, 0, 255, "Magenta"),
            (0, 255, 255, "Cyan"),
            (255, 255, 255, "White"),
            (0, 0, 0, "Off"),
        ]

        for led_id in self.led.available_leds[:1]:  # Test first LED
            for r, g, b, name in test_colors:
                self.led.set_rgb_color(led_id, r, g, b)
                time.sleep(0.5)  # Standard delay for color change

                # Read back values
                read_r, read_g, read_b = self.led.get_rgb_color(led_id)

                # Due to 8-bit to 4-bit conversion, values may differ slightly
                # Each 4-bit step is ~17 in 8-bit space (255/15)
                tolerance = 17
                self.assertAlmostEqual(read_r, r, delta=tolerance, msg=f"{name} red mismatch")
                self.assertAlmostEqual(read_g, g, delta=tolerance, msg=f"{name} green mismatch")
                self.assertAlmostEqual(read_b, b, delta=tolerance, msg=f"{name} blue mismatch")

                print(f"  ✓ LED {led_id} {name}: set({r},{g},{b}) read({read_r},{read_g},{read_b})")

    def test_rgb_protocol_conversion(self):
        """Test 8-bit to 4-bit RGB protocol conversion."""
        # The hardware uses 4-bit RGB (0-15), but sysfs accepts 8-bit (0-255)
        # Test that values snap to 16 discrete levels

        led_id = self.led.available_leds[0]

        # Test specific values that should map to 4-bit levels
        test_values = [
            (0, 0),  # 0 -> 0
            (17, 17),  # ~1/15 * 255
            (34, 34),  # ~2/15 * 255
            (128, 136),  # ~8/15 * 255 (128 should map to level 8)
            (255, 255),  # 15/15 * 255
        ]

        for input_val, expected_range_center in test_values:
            self.led.set_rgb_color(led_id, input_val, 0, 0)
            time.sleep(0.2)  # Quick delay for read-back
            read_r, _, _ = self.led.get_rgb_color(led_id)

            # Check if value is within expected 4-bit quantization range
            self.assertAlmostEqual(
                read_r,
                expected_range_center,
                delta=17,
                msg=f"4-bit conversion failed for {input_val}",
            )
            print(f"  ✓ 8-bit {input_val} -> 4-bit level -> 8-bit {read_r}")

    def test_rgb_write_performance(self):
        """Measure RGB write performance to hardware."""
        led_id = self.led.available_leds[0]

        # Measure single write time
        _, write_time = self.measure_time(self.led.set_rgb_color, led_id, 255, 128, 64)
        print(f"  ✓ Single RGB write time: {write_time:.2f}ms")
        self.assertLess(write_time, 50, "RGB write too slow (>50ms)")

        # Measure rapid color changes
        start = time.perf_counter()
        for i in range(10):
            self.led.set_rgb_color(led_id, i * 25, 255 - i * 25, i * 12)
        elapsed = (time.perf_counter() - start) * 1000
        avg_time = elapsed / 10

        print(f"  ✓ Average RGB write time (10 changes): {avg_time:.2f}ms")
        self.assertLess(avg_time, 20, "Average RGB write too slow (>20ms)")

    def test_multi_led_rgb_control(self):
        """Test independent RGB control of multiple LEDs."""
        if len(self.led.available_leds) < 2:
            self.skipTest("Multiple LEDs not available")

        # Set different colors on different LEDs
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]

        for i, led_id in enumerate(self.led.available_leds[:4]):
            color = colors[i % len(colors)]
            self.led.set_rgb_color(led_id, *color)
            time.sleep(0.2)  # Quick delay for hardware to process

        # Verify each LED maintains its color
        for i, led_id in enumerate(self.led.available_leds[:4]):
            expected = colors[i % len(colors)]
            actual = self.led.get_rgb_color(led_id)

            for j in range(3):
                self.assertAlmostEqual(
                    actual[j],
                    expected[j],
                    delta=17,
                    msg=f"LED {led_id} color component {j} mismatch",
                )

            print(f"  ✓ LED {led_id} maintains color {actual}")


class TestAnimationHardware(HardwareTestBase):
    """Test animation modes on actual hardware."""

    def test_animation_modes(self):
        """Test all animation modes on hardware."""
        led_id = self.led.available_leds[0]
        modes = ["static", "blink", "fade", "rainbow"]

        # Set a visible color first
        self.led.set_rgb_color(led_id, 0, 255, 0)  # Green

        for mode in modes:
            self.led.set_animation_mode(led_id, mode, 500)
            time.sleep(0.5)  # Standard delay for mode change

            read_mode, read_timing = self.led.get_animation_mode(led_id)
            self.assertEqual(read_mode, mode, f"Mode {mode} not set correctly")
            self.assertEqual(read_timing, 500, f"Timing not set correctly for {mode}")

            print(f"  ✓ Animation mode '{mode}' set successfully")

            # Let animation run briefly for visual confirmation
            time.sleep(1.0)

    def test_animation_timing_values(self):
        """Test all valid timing values."""
        led_id = self.led.available_leds[0]
        valid_timings = [100, 200, 500, 1000]

        self.led.set_rgb_color(led_id, 255, 0, 0)  # Red

        for timing in valid_timings:
            self.led.set_animation_mode(led_id, "blink", timing)
            time.sleep(0.2)  # Quick delay for read-back

            _, read_timing = self.led.get_animation_mode(led_id)
            self.assertEqual(read_timing, timing, f"Timing {timing}ms not set")

            print(f"  ✓ Timing {timing}ms set successfully")

    def test_animation_timing_measurement(self):
        """Measure actual animation timing accuracy."""
        if not hasattr(self, "visual_test"):
            self.skipTest("Visual timing test - run with --visual flag")

        led_id = self.led.available_leds[0]
        self.led.set_rgb_color(led_id, 255, 255, 255)  # White
        self.led.set_animation_mode(led_id, "blink", 500)

        print("  ⏱ Observing blink timing (5 seconds)...")
        time.sleep(5)
        print("  ✓ Visual timing test complete")


class TestLEDTriggers(HardwareTestBase):
    """Test LED trigger functionality on hardware."""

    def test_available_triggers(self):
        """Test listing available triggers."""
        led_id = self.led.available_leds[0]
        triggers = self.led.get_available_triggers(led_id)

        self.assertIsInstance(triggers, list)
        self.assertIn("none", triggers, "Default 'none' trigger missing")

        print(f"  ✓ Available triggers: {triggers}")

        # Check for RGB triggers
        rgb_triggers = ["heartbeat-rgb", "breathing-rgb", "rainbow-rgb"]
        for trigger in rgb_triggers:
            if trigger in triggers:
                print(f"  ✓ RGB trigger '{trigger}' available")

    def test_trigger_activation(self):
        """Test activating and deactivating triggers."""
        led_id = self.led.available_leds[0]
        available = self.led.get_available_triggers(led_id)

        # Test each available RGB trigger
        test_triggers = ["heartbeat-rgb", "breathing-rgb", "rainbow-rgb"]

        for trigger in test_triggers:
            if trigger not in available:
                print(f"  ⚠ Trigger '{trigger}' not available, skipping")
                continue

            # Activate trigger
            self.led.set_trigger(led_id, trigger)
            time.sleep(1.0)  # Trigger operations need more time

            current = self.led.get_trigger(led_id)
            self.assertEqual(current, trigger, f"Trigger {trigger} not activated")

            print(f"  ✓ Trigger '{trigger}' activated")

            # Let it run briefly
            time.sleep(1.0)

            # Deactivate
            self.led.set_trigger(led_id, "none")
            time.sleep(1.0)  # Trigger operations need more time

            current = self.led.get_trigger(led_id)
            self.assertEqual(current, "none", "Trigger not deactivated")

            print(f"  ✓ Trigger '{trigger}' deactivated")


class TestBrightnessControl(HardwareTestBase):
    """Test brightness control on hardware."""

    def test_brightness_levels(self):
        """Test various brightness levels."""
        led_id = self.led.available_leds[0]

        # Set a color first
        self.led.set_rgb_color(led_id, 255, 255, 255)  # White

        test_levels = [0, 64, 128, 192, 255]

        for level in test_levels:
            self.led.set_brightness(led_id, level)
            time.sleep(0.2)  # Quick delay for read-back

            read_level = self.led.get_brightness(led_id)
            # Allow some tolerance for hardware quantization
            self.assertAlmostEqual(read_level, level, delta=17, msg=f"Brightness {level} mismatch")

            print(f"  ✓ Brightness {level} -> {read_level}")
            time.sleep(0.5)  # Brief pause to observe

    def test_brightness_with_rgb(self):
        """Test brightness interaction with RGB values."""
        led_id = self.led.available_leds[0]

        # Set RGB color
        self.led.set_rgb_color(led_id, 255, 128, 64)
        time.sleep(0.5)  # Standard delay for color change

        # Set brightness to 50%
        self.led.set_brightness(led_id, 128)
        time.sleep(0.5)  # Standard delay for brightness change

        brightness = self.led.get_brightness(led_id)
        self.assertAlmostEqual(brightness, 128, delta=17)

        # RGB values should be preserved
        r, g, b = self.led.get_rgb_color(led_id)
        print(f"  ✓ RGB ({r},{g},{b}) with brightness {brightness}")


class TestMultiLEDOperations(HardwareTestBase):
    """Test operations across multiple LEDs."""

    def test_set_color_all(self):
        """Test setting same color on all LEDs."""
        if len(self.led.available_leds) < 2:
            self.skipTest("Multiple LEDs not available")

        # Set all LEDs to blue
        self.led.set_color_all(0, 128, 255)
        time.sleep(0.5)  # Standard delay for color change

        # Verify all LEDs have the same color
        for led_id in self.led.available_leds:
            r, g, b = self.led.get_rgb_color(led_id)
            self.assertAlmostEqual(r, 0, delta=17)
            self.assertAlmostEqual(g, 128, delta=17)
            self.assertAlmostEqual(b, 255, delta=17)
            print(f"  ✓ LED {led_id} set to ({r},{g},{b})")

    def test_set_brightness_all(self):
        """Test setting same brightness on all LEDs."""
        if len(self.led.available_leds) < 2:
            self.skipTest("Multiple LEDs not available")

        # Set all LEDs to white first
        self.led.set_color_all(255, 255, 255)
        time.sleep(0.5)  # Standard delay for color change

        # Set all to 50% brightness
        self.led.set_brightness_all(128)
        time.sleep(0.5)  # Standard delay for brightness change

        # Verify
        for led_id in self.led.available_leds:
            brightness = self.led.get_brightness(led_id)
            self.assertAlmostEqual(brightness, 128, delta=17)
            print(f"  ✓ LED {led_id} brightness: {brightness}")

    def test_turn_off_all(self):
        """Test turning off all LEDs."""
        # Set all LEDs to different colors
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]

        for i, led_id in enumerate(self.led.available_leds):
            color = colors[i % len(colors)]
            self.led.set_rgb_color(led_id, *color)
            self.led.set_brightness(led_id, 200)

        time.sleep(1.0)  # Show colors briefly

        # Turn off all
        self.led.turn_off_all()
        time.sleep(0.5)  # Standard delay for turning off

        # Verify all are off
        for led_id in self.led.available_leds:
            r, g, b = self.led.get_rgb_color(led_id)
            brightness = self.led.get_brightness(led_id)

            self.assertEqual(r, 0, f"LED {led_id} red not off")
            self.assertEqual(g, 0, f"LED {led_id} green not off")
            self.assertEqual(b, 0, f"LED {led_id} blue not off")
            self.assertEqual(brightness, 0, f"LED {led_id} brightness not off")

            print(f"  ✓ LED {led_id} turned off")


class TestPerformanceAndStress(HardwareTestBase):
    """Test performance and stress scenarios."""

    def test_rapid_color_changes(self):
        """Test rapid color changes for performance."""
        led_id = self.led.available_leds[0]

        # Let hardware settle before performance test
        time.sleep(2.0)

        start = time.perf_counter()
        changes = 100

        for i in range(changes):
            r = (i * 7) % 256
            g = (i * 13) % 256
            b = (i * 17) % 256
            self.led.set_rgb_color(led_id, r, g, b)

        elapsed = time.perf_counter() - start
        rate = changes / elapsed

        print(f"  ✓ Completed {changes} color changes in {elapsed:.2f}s")
        print(f"  ✓ Rate: {rate:.1f} changes/second")

        self.assertGreater(rate, 50, "Color change rate too slow (<50/s)")

    def test_mode_switching_stress(self):
        """Test rapid mode switching."""
        led_id = self.led.available_leds[0]
        modes = ["static", "blink", "fade", "rainbow"]

        # Let hardware settle before performance test
        time.sleep(2.0)

        self.led.set_rgb_color(led_id, 255, 0, 255)  # Magenta

        start = time.perf_counter()
        switches = 40

        for i in range(switches):
            mode = modes[i % len(modes)]
            self.led.set_animation_mode(led_id, mode, 200)

        elapsed = time.perf_counter() - start
        rate = switches / elapsed

        print(f"  ✓ Completed {switches} mode switches in {elapsed:.2f}s")
        print(f"  ✓ Rate: {rate:.1f} switches/second")

        # Verify final state is consistent
        final_mode, _ = self.led.get_animation_mode(led_id)
        expected_mode = modes[(switches - 1) % len(modes)]
        self.assertEqual(final_mode, expected_mode, "Mode state inconsistent after stress")

    def test_concurrent_multi_led_operations(self):
        """Test concurrent operations on multiple LEDs."""
        if len(self.led.available_leds) < 2:
            self.skipTest("Multiple LEDs not available")

        # Let hardware settle before performance test
        time.sleep(2.0)

        num_leds = min(4, len(self.led.available_leds))
        operations = 50

        start = time.perf_counter()

        for i in range(operations):
            led_id = self.led.available_leds[i % num_leds]

            # Alternate between different operations
            if i % 3 == 0:
                self.led.set_rgb_color(led_id, (i * 7) % 256, (i * 11) % 256, (i * 13) % 256)
            elif i % 3 == 1:
                self.led.set_brightness(led_id, (i * 17) % 256)
            else:
                modes = ["static", "blink", "fade", "rainbow"]
                self.led.set_animation_mode(led_id, modes[i % 4], 200)

        elapsed = time.perf_counter() - start
        rate = operations / elapsed

        print(f"  ✓ Completed {operations} multi-LED operations in {elapsed:.2f}s")
        print(f"  ✓ Rate: {rate:.1f} operations/second")


class TestErrorHandling(HardwareTestBase):
    """Test error handling and recovery."""

    def test_invalid_led_id(self):
        """Test handling of invalid LED IDs."""
        invalid_ids = [99, 100, 255, -1]

        for led_id in invalid_ids:
            with self.assertRaises(LEDError):
                self.led.set_rgb_color(led_id, 255, 0, 0)
            print(f"  ✓ Invalid LED ID {led_id} rejected")

    def test_invalid_rgb_values(self):
        """Test handling of invalid RGB values."""
        led_id = self.led.available_leds[0]

        invalid_values = [
            (256, 0, 0),  # R > 255
            (0, -1, 0),  # G < 0
            (0, 0, 300),  # B > 255
            (-10, -10, -10),  # All negative
        ]

        for r, g, b in invalid_values:
            with self.assertRaises(LEDError):
                self.led.set_rgb_color(led_id, r, g, b)
            print(f"  ✓ Invalid RGB ({r},{g},{b}) rejected")

    def test_invalid_brightness(self):
        """Test handling of invalid brightness values."""
        led_id = self.led.available_leds[0]

        invalid_values = [256, 300, -1, -100]

        for brightness in invalid_values:
            with self.assertRaises(LEDError):
                self.led.set_brightness(led_id, brightness)
            print(f"  ✓ Invalid brightness {brightness} rejected")

    def test_invalid_animation_mode(self):
        """Test handling of invalid animation modes."""
        led_id = self.led.available_leds[0]

        invalid_modes = ["invalid", "test", "random", ""]

        for mode in invalid_modes:
            with self.assertRaises(LEDError):
                self.led.set_animation_mode(led_id, mode)
            print(f"  ✓ Invalid mode '{mode}' rejected")

    def test_recovery_after_errors(self):
        """Test that LED remains functional after errors."""
        led_id = self.led.available_leds[0]

        # Cause an error
        try:
            self.led.set_rgb_color(led_id, 300, 300, 300)
        except LEDError:
            pass

        # Verify LED still works
        self.led.set_rgb_color(led_id, 0, 255, 0)
        time.sleep(0.5)  # Standard delay for recovery test
        r, g, b = self.led.get_rgb_color(led_id)

        self.assertAlmostEqual(g, 255, delta=17, msg="LED not functional after error")
        print("  ✓ LED functional after error recovery")


class TestProtocolCompliance(HardwareTestBase):
    """Test protocol compliance and hardware limits."""

    def test_4bit_rgb_quantization(self):
        """Test that RGB values quantize to 4-bit levels correctly."""
        led_id = self.led.available_leds[0]

        # 4-bit means 16 levels (0-15), mapped to 0-255
        # Each level is approximately 17 units (255/15)

        # Test all 16 levels for red channel
        for level in range(16):
            expected_8bit = (level * 255) // 15

            self.led.set_rgb_color(led_id, expected_8bit, 0, 0)
            time.sleep(0.2)  # Quick delay for protocol test

            read_r, _, _ = self.led.get_rgb_color(led_id)

            # Check if read value is close to expected quantized value
            self.assertAlmostEqual(
                read_r, expected_8bit, delta=17, msg=f"Level {level} quantization incorrect"
            )

            print(f"  ✓ Level {level}: {expected_8bit} -> {read_r}")

    def test_led_id_limit(self):
        """Test that LED IDs are limited to 4-bit range (0-15)."""
        # Protocol supports max 16 LEDs (4-bit ID)
        self.assertLessEqual(
            len(self.led.available_leds), 16, "More than 16 LEDs detected (exceeds 4-bit limit)"
        )

        for led_id in self.led.available_leds:
            self.assertGreaterEqual(led_id, 0, f"LED ID {led_id} < 0")
            self.assertLessEqual(led_id, 15, f"LED ID {led_id} > 15")

        print("  ✓ All LED IDs within 4-bit range (0-15)")

    def test_timing_value_constraints(self):
        """Test that timing values are constrained to valid set."""
        led_id = self.led.available_leds[0]

        # Valid timings: 100, 200, 500, 1000 ms
        # Test that invalid values get rounded to nearest valid
        test_cases = [
            (50, 100),  # Below min -> 100
            (150, 100),  # Between 100-200 -> 100 (nearest)
            (350, 200),  # Between 200-500 -> 200 (nearest)
            (750, 500),  # Between 500-1000 -> 500 (nearest)
            (1500, 1000),  # Above max -> 1000
        ]

        for input_timing, expected_timing in test_cases:
            self.led.set_animation_mode(led_id, "blink", input_timing)
            time.sleep(0.2)  # Quick delay for timing test

            _, read_timing = self.led.get_animation_mode(led_id)
            self.assertEqual(
                read_timing,
                expected_timing,
                f"Timing {input_timing} not rounded to {expected_timing}",
            )

            print(f"  ✓ Timing {input_timing}ms -> {expected_timing}ms")


def run_hardware_tests(verbose=False, pattern=None, visual=False):
    """Run the hardware test suite with options."""

    print("\n" + "=" * 60)
    print("SAM LED HARDWARE TEST SUITE")
    print("=" * 60)
    print("Testing actual hardware via sysfs interface")
    print("Requires: Root privileges and SAM hardware")
    print("=" * 60 + "\n")

    # Check for root
    if os.geteuid() != 0:
        print("⚠️  WARNING: Not running as root. Some tests may fail.")
        print("   Run with: sudo python led_test.py\n")

    # Configure test runner
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Test classes in execution order
    test_classes = [
        TestHardwareDetection,
        TestRGBHardwareControl,
        TestAnimationHardware,
        TestLEDTriggers,
        TestBrightnessControl,
        TestMultiLEDOperations,
        TestPerformanceAndStress,
        TestErrorHandling,
        TestProtocolCompliance,
    ]

    # Add visual test flag if requested
    if visual:
        HardwareTestBase.visual_test = True

    # Load tests based on pattern
    for test_class in test_classes:
        if pattern:
            # Filter by pattern
            for test_name in loader.getTestCaseNames(test_class):
                if pattern.lower() in test_name.lower():
                    suite.addTest(test_class(test_name))
        else:
            # Load all tests
            suite.addTests(loader.loadTestsFromTestCase(test_class))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2 if verbose else 1)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 60)
    print("HARDWARE TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")

    if result.wasSuccessful():
        print("\n✅ All hardware tests passed successfully!")
    else:
        print("\n❌ Some hardware tests failed. Check output above.")

    print("=" * 60 + "\n")

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hardware Integration Tests for SAM LED Module")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("-p", "--pattern", type=str, help="Run only tests matching pattern")
    parser.add_argument(
        "--visual", action="store_true", help="Enable visual timing tests (requires observation)"
    )
    parser.add_argument("--list", action="store_true", help="List available test categories")

    args = parser.parse_args()

    if args.list:
        print("\nAvailable test categories:")
        print("  - hardware    : Hardware detection tests")
        print("  - rgb         : RGB color control tests")
        print("  - animation   : Animation mode tests")
        print("  - trigger     : LED trigger tests")
        print("  - brightness  : Brightness control tests")
        print("  - multi       : Multi-LED operation tests")
        print("  - performance : Performance and stress tests")
        print("  - error       : Error handling tests")
        print("  - protocol    : Protocol compliance tests")
        print("\nUse -p/--pattern to run specific categories")
        sys.exit(0)

    sys.exit(run_hardware_tests(verbose=args.verbose, pattern=args.pattern, visual=args.visual))
