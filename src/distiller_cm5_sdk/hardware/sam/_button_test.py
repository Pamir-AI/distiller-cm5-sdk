#!/usr/bin/env python3
"""
Test script for the SAM module SDK.
This demonstrates initialization, button callbacks, and LED control with task completion.
"""

import time
import sys
import signal
from sam import SAM, ButtonType

def main():
    """Main test function to demonstrate SAM module functionality."""
    print("SAM Module Test Script")
    print("---------------------")
    print("This script will test the basic functionality of the SAM module.")
    print("Press Ctrl+C to exit the test.\n")
    
    # Initialize the SAM module
    try:
        print("Initializing SAM module...")
        sam = SAM()
        print("SAM module initialized successfully!")
    except RuntimeError as e:
        print(f"Failed to initialize SAM module: {e}")
        return 1
    
    # Connect to the SAM module
    print("Connecting to SAM module...")
    if not sam.connect():
        print("Failed to connect to SAM module.")
        return 1
    print("Connected to SAM module successfully!")
    
    # Setup button callbacks
    def button_up_handler():
        print("UP button pressed!")
        # Light up blue when UP is pressed - wait for any running task to complete
        if sam.is_led_task_running():
            print("Waiting for previous LED task to complete...")
            sam.wait_for_led_task_completion(timeout=5.0)
        sam.set_led_color(0, 0, 255, brightness=0.5)
        
    def button_down_handler():
        print("DOWN button pressed!")
        # Light up green when DOWN is pressed - wait for any running task to complete
        if sam.is_led_task_running():
            print("Waiting for previous LED task to complete...")
            sam.wait_for_led_task_completion(timeout=5.0)
        sam.set_led_color(0, 255, 0, brightness=0.5)
        
    def button_select_handler():
        print("SELECT button pressed!")
        # Light up red when SELECT is pressed - wait for any running task to complete
        if sam.is_led_task_running():
            print("Waiting for previous LED task to complete...")
            sam.wait_for_led_task_completion(timeout=5.0)
        sam.set_led_color(255, 0, 0, brightness=0.5)
        
    def button_shutdown_handler():
        print("SHUTDOWN signal received!")
        # Fade to white - wait for any running task to complete
        if sam.is_led_task_running():
            print("Waiting for previous LED task to complete...")
            sam.wait_for_led_task_completion(timeout=5.0)
        sam.fade_led(255, 255, 255, steps=10, duration=2.0)
    
    # Register button callbacks
    print("Registering button callbacks...")
    sam.register_button_callback(ButtonType.UP, button_up_handler)
    sam.register_button_callback(ButtonType.DOWN, button_down_handler)
    sam.register_button_callback(ButtonType.SELECT, button_select_handler)
    sam.register_button_callback(ButtonType.SHUTDOWN, button_shutdown_handler)
    
    
    # Wait for button presses
    print("\nTest completed. Now waiting for button presses...")
    print("Press UP, DOWN, or SELECT buttons on your device to see callbacks in action.")
    print("Press Ctrl+C to exit.")
    
    try:
        # Keep the main thread alive to continue receiving button events
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        # Cleanup
        print("\nCleaning up...")
        sam.disconnect()
    return 0

if __name__ == "__main__":
    sys.exit(main())
