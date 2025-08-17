#!/usr/bin/env python3
"""
Real camera test for the camera.py module in the CM5 SDK.
This script tests all available functions with a real camera and saves captured images for review.
"""

import os
import time

from camera import Camera


def main():
    """Main test function for testing all camera functionality with real hardware."""
    print("=== CM5 Camera Real Hardware Test ===")

    # Create output directory for captured images
    output_dir = "camera_test_output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Initialize camera with real hardware
    print("\n1. Initializing camera...")
    camera = Camera(
        resolution=(1280, 720), framerate=30, rotation=0, format="bgr", auto_check_config=True
    )
    print("  - Camera initialized successfully")

    # Test system configuration
    print("\n2. Testing system configuration...")
    try:
        if camera.check_system_config():
            print("  - System configuration check passed")
    except Exception as e:
        print(f"  - System configuration check failed: {e}")

    # Test available settings
    print("\n3. Testing available camera settings...")
    settings = camera.get_available_settings()
    print(f"  - Available settings: {settings}")

    # Test getting current settings
    print("\n4. Testing current camera settings...")
    for setting in settings:
        try:
            value = camera.get_setting(setting)
            print(f"  - {setting}: {value}")
        except Exception as e:
            print(f"  - Failed to get {setting}: {e}")

    # Test adjusting settings
    print("\n5. Testing setting adjustments...")
    test_settings = {"brightness": 60, "contrast": 60, "saturation": 60}

    # Store original values
    original_values = {}
    for setting, test_value in test_settings.items():
        try:
            original_values[setting] = camera.get_setting(setting)
            success = camera.adjust_setting(setting, test_value)
            if success:
                new_value = camera.get_setting(setting)
                print(f"  - Adjusted {setting}: {original_values[setting]} -> {new_value}")
            else:
                print(f"  - Failed to adjust {setting}")
        except Exception as e:
            print(f"  - Error adjusting {setting}: {e}")

    # Test different formats
    print("\n6. Testing different formats...")
    formats = ["bgr", "rgb", "gray"]
    for fmt in formats:
        try:
            print(f"  - Setting format to {fmt}")
            camera.format = fmt
            frame = camera.get_frame()
            filename = f"{output_dir}/format_{fmt}.jpg"
            if fmt == "gray":
                # Convert grayscale to BGR for saving
                frame_save = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            elif fmt == "rgb":
                # Convert RGB to BGR for saving
                frame_save = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            else:
                frame_save = frame
            cv2.imwrite(filename, frame_save)
            print(f"  - Saved {fmt} format image to {filename}")
            print(f"  - Frame shape: {frame.shape}")
        except Exception as e:
            print(f"  - Error testing format {fmt}: {e}")

    # Reset to BGR for remaining tests
    camera.format = "bgr"

    # Test rotation
    print("\n7. Testing rotation settings...")
    rotations = [0, 90, 180, 270]
    for rotation in rotations:
        try:
            print(f"  - Setting rotation to {rotation}")
            camera.rotation = rotation
            frame = camera.get_frame()
            filename = f"{output_dir}/rotation_{rotation}.jpg"
            cv2.imwrite(filename, frame)
            print(f"  - Saved rotation {rotation} image to {filename}")
            print(f"  - Frame shape: {frame.shape}")
        except Exception as e:
            print(f"  - Error testing rotation {rotation}: {e}")

    # Reset rotation
    camera.rotation = 0

    # Test capturing single image
    print("\n8. Testing image capture...")
    try:
        filename = f"{output_dir}/capture_test.jpg"
        frame = camera.capture_image(filepath=filename)
        print(f"  - Captured and saved image to {filename}")
        print(f"  - Frame shape: {frame.shape}")
    except Exception as e:
        print(f"  - Error capturing image: {e}")

    # Test stream with callbacks
    print("\n9. Testing stream with callbacks...")
    frames_received = []

    def stream_callback(frame):
        frames_received.append(frame.shape)
        if len(frames_received) == 1:
            # Save first frame
            cv2.imwrite(f"{output_dir}/stream_callback.jpg", frame)
            print(f"  - Saved stream callback frame to {output_dir}/stream_callback.jpg")

    try:
        camera.start_stream(callback=stream_callback)
        print("  - Stream started with callback")
        time.sleep(2)  # Wait to receive frames
        camera.stop_stream()
        print(f"  - Stream stopped after receiving {len(frames_received)} frames")
    except Exception as e:
        print(f"  - Error testing stream callback: {e}")

    # Test starting and stopping stream
    print("\n10. Testing start/stop stream...")
    try:
        camera.start_stream()
        print("  - Stream started")
        time.sleep(1)
        frame = camera.get_frame()
        filename = f"{output_dir}/stream_frame.jpg"
        cv2.imwrite(filename, frame)
        print(f"  - Got frame from stream and saved to {filename}")
        camera.stop_stream()
        print("  - Stream stopped")
    except Exception as e:
        print(f"  - Error testing stream: {e}")

    # Restore original settings
    print("\n11. Restoring original settings...")
    for setting, original_value in original_values.items():
        try:
            camera.adjust_setting(setting, original_value)
            print(f"  - Restored {setting} to {original_value}")
        except Exception as e:
            print(f"  - Error restoring {setting}: {e}")

    # Close the camera
    print("\n12. Closing camera...")
    camera.close()
    print("  - Camera closed")

    print("\n=== Test completed successfully ===")
    print(f"All captured images saved to {os.path.abspath(output_dir)}")


if __name__ == "__main__":
    import cv2  # Import here to handle import error explicitly

    main()
