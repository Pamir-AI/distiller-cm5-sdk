import serial
import threading
import json
import time
import os
import sys
from enum import Enum
from typing import Callable, Dict, Optional, Union, List, Tuple


class ButtonType(Enum):
    """Enum representing the different button types on the device."""
    UP = "BTN_UP"
    DOWN = "BTN_DOWN"
    SELECT = "BTN_SELECT"
    SHUTDOWN = "SHUT_DOWN"

class SAM:
    """
    SDK interface for SAM module (RP2040 microcontroller).
    Provides functionality to interact with buttons and control the RGB LED.
    """
    
    def __init__(self, timeout: float = 1.0):
        """
        Initialize the SAM module interface.
        
        Args:
            timeout: Serial timeout in seconds
            
        Raises:
            RuntimeError: If the UART device /dev/ttyAMA2 does not exist
        """
        self._port = "/dev/ttyAMA2"
        self._baudrate = 115200
        self._timeout = timeout
        
        # Check if the required UART device exists
        if not os.path.exists(self._port):
            error_msg = (
                f"ERROR: {self._port} does not exist.\n"
                "Please make sure the UART2 is enabled in your config.txt by adding:\n"
                "dtoverlay=uart2,pin_tx=4,pin_rx=5\n"
                "Then reboot your device."
            )
            print(error_msg, file=sys.stderr)
            raise RuntimeError(error_msg)
            
        self._serial = None
        self._running = False
        self._read_thread = None
        self._button_callbacks: Dict[ButtonType, List[Callable]] = {
            ButtonType.UP: [],
            ButtonType.DOWN: [],
            ButtonType.SELECT: [],
            ButtonType.SHUTDOWN: []
        }
        self._button_state_map = {
            ButtonType.UP.value: 0b1,
            ButtonType.DOWN.value: 0b10,
            ButtonType.SELECT.value: 0b100,
            ButtonType.SHUTDOWN.value: 0b1000
        }
        # LED task status tracking
        self._led_task_running = False
        self._led_task_completed = threading.Event()
        self._led_task_completed.set()  # Initially no task is running
        
    def connect(self) -> bool:
        """
        Connect to the SAM module via serial.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                timeout=self._timeout
            )
            self._running = True
            self._read_thread = threading.Thread(target=self._read_serial, daemon=True)
            self._read_thread.start()
            return True
        except serial.SerialException as e:
            print(f"Failed to connect to SAM module: {e}")
            return False
    
    def disconnect(self) -> None:
        """Close the connection to the SAM module."""
        self._running = False
        if self._read_thread:
            self._read_thread.join(timeout=1.0)
        if self._serial and self._serial.is_open:
            self._serial.close()
    
    def _read_serial(self) -> None:
        """Read data from serial port and process button events."""
        if not self._serial:
            return
            
        buffer = ""
        while self._running:
            try:
                if self._serial.in_waiting:
                    data = self._serial.read(1).decode('utf-8', errors='replace')
                    buffer += data
                    
                    if '\n' in buffer:
                        lines = buffer.split('\n')
                        buffer = lines[-1]  # Keep the incomplete line
                        
                        for line in lines[:-1]:  # Process complete lines
                            line = line.strip()
                            if not line:
                                continue
                                
                            try:
                                # Try parsing as integer for button state
                                state = int(line)
                                self._process_button_state(state)
                            except ValueError:
                                # Check for LED task completion message
                                if "[Task] Neopixel Completed" in line:
                                    self._led_task_running = False
                                    self._led_task_completed.set()
                                    print("LED task completed")
                                # Other messages
                                elif "[RP2040 DEBUG]" in line:
                                    print(f"SAM Debug: {line}")
                                elif "StartScreen" in line:
                                    print("SAM starting screen")
                                else:
                                    print(f"SAM message: {line}")
            except Exception as e:
                print(f"Error reading from SAM: {e}")
                time.sleep(0.1)
            
            time.sleep(0.01)  # Small sleep to prevent CPU hogging
    
    def _process_button_state(self, state: int) -> None:
        """
        Process button state received from SAM and trigger callbacks.
        
        Args:
            state: Integer representing button state bitmask
        """
        for button_type in ButtonType:
            button_mask = self._button_state_map.get(button_type.value, 0)
            if state & button_mask:
                for callback in self._button_callbacks[button_type]:
                    try:
                        callback()
                    except Exception as e:
                        print(f"Error in {button_type.name} button callback: {e}")
    
    def register_button_callback(self, button: ButtonType, callback: Callable) -> None:
        """
        Register a callback function for a specific button.
        
        Args:
            button: The button type to register for
            callback: Function to call when button is pressed
        """
        if button in self._button_callbacks:
            self._button_callbacks[button].append(callback)
    
    def unregister_button_callback(self, button: ButtonType, callback: Callable) -> bool:
        """
        Unregister a callback function for a specific button.
        
        Args:
            button: The button type to unregister from
            callback: Function to remove from callbacks
            
        Returns:
            bool: True if callback was removed, False if not found
        """
        if button in self._button_callbacks and callback in self._button_callbacks[button]:
            self._button_callbacks[button].remove(callback)
            return True
        return False
    
    def wait_for_led_task_completion(self, timeout: float = None) -> bool:
        """
        Wait for any ongoing LED task to complete.
        
        Args:
            timeout: Maximum time to wait in seconds (None for no timeout)
            
        Returns:
            bool: True if task completed, False if timeout occurred
        """
        return self._led_task_completed.wait(timeout)
    
    def is_led_task_running(self) -> bool:
        """
        Check if an LED task is currently running.
        
        Returns:
            bool: True if a task is running, False otherwise
        """
        return self._led_task_running
    
    def set_led_color(self, r: int, g: int, b: int, brightness: float = 0.5, delay: float = 0.0, 
                     wait_for_completion: bool = False, timeout: float = None) -> bool:
        """
        Set the RGB LED color.
        
        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
            brightness: LED brightness (0.0-1.0)
            delay: Delay before next color change (seconds)
            wait_for_completion: Whether to wait for task completion
            timeout: Maximum time to wait if wait_for_completion is True
            
        Returns:
            bool: True if command was sent successfully, False otherwise
        """
        return self.set_led_sequence(
            [{
                "r": r, 
                "g": g, 
                "b": b, 
                "brightness": brightness, 
                "delay": delay
            }],
            wait_for_completion=wait_for_completion,
            timeout=timeout
        )
    
    def set_led_sequence(self, colors: List[Dict[str, Union[int, float]]], 
                        wait_for_completion: bool = False, timeout: float = None) -> bool:
        """
        Set a sequence of colors for the RGB LED.
        
        Args:
            colors: List of color dictionaries with keys:
                   r, g, b: RGB values (0-255)
                   brightness: LED brightness (0.0-1.0)
                   delay: Delay before next color (seconds)
            wait_for_completion: Whether to wait for the previous task to complete
            timeout: Maximum time to wait for previous task completion
                   
        Returns:
            bool: True if command was sent successfully, False otherwise
        """
        if not self._serial or not self._serial.is_open:
            return False
        
        # Wait for any ongoing task to complete if requested
        if self._led_task_running:
            if wait_for_completion:
                if not self._led_task_completed.wait(timeout):
                    print("Timeout waiting for LED task completion")
                    return False
            else:
                print("Cannot send command: LED task already running")
                return False
                
        # Mark new task as started
        self._led_task_completed.clear()
        self._led_task_running = True
        
        sequence = {}
        for i, color in enumerate(colors):
            sequence[str(i)] = [
                color.get("r", 0),
                color.get("g", 0),
                color.get("b", 0),
                color.get("brightness", 0.5),
                color.get("delay", 0.0)
            ]
        
        command = {
            "Function": "NeoPixel",
            "colors": sequence
        }
        
        try:
            cmd_bytes = json.dumps(command) + "\n"
            self._serial.write(cmd_bytes.encode())
            self._serial.flush()
            
            # Wait for task completion if requested
            if wait_for_completion:
                if not self._led_task_completed.wait(timeout):
                    print("Timeout waiting for LED task completion")
                    return False
                    
            return True
        except Exception as e:
            print(f"Error sending LED command: {e}")
            self._led_task_running = False
            self._led_task_completed.set()
            return False
    
    def blink_led(self, r: int, g: int, b: int, count: int = 3, 
                 on_time: float = 0.5, off_time: float = 0.5, 
                 brightness: float = 0.5, wait_for_completion: bool = False,
                 timeout: float = None) -> bool:
        """
        Blink the RGB LED.
        
        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
            count: Number of blinks
            on_time: Time LED is on for each blink (seconds)
            off_time: Time LED is off for each blink (seconds)
            brightness: LED brightness (0.0-1.0)
            wait_for_completion: Whether to wait for task completion
            timeout: Maximum time to wait if wait_for_completion is True
            
        Returns:
            bool: True if command was sent successfully, False otherwise
        """
        sequence = []
        for _ in range(count):
            # On state
            sequence.append({
                "r": r, 
                "g": g, 
                "b": b, 
                "brightness": brightness, 
                "delay": on_time
            })
            # Off state
            sequence.append({
                "r": 0, 
                "g": 0, 
                "b": 0, 
                "brightness": 0, 
                "delay": off_time
            })
        
        return self.set_led_sequence(
            sequence,
            wait_for_completion=wait_for_completion,
            timeout=timeout
        )
    
    def fade_led(self, r: int, g: int, b: int, 
                steps: int = 10, duration: float = 1.0,
                final_brightness: float = 1.0, wait_for_completion: bool = False,
                timeout: float = None) -> bool:
        """
        Fade in the RGB LED.
        
        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
            steps: Number of brightness steps
            duration: Total fade duration (seconds)
            final_brightness: Final brightness value (0.0-1.0)
            wait_for_completion: Whether to wait for task completion
            timeout: Maximum time to wait if wait_for_completion is True
            
        Returns:
            bool: True if command was sent successfully, False otherwise
        """
        step_time = duration / steps
        sequence = []
        
        for i in range(steps):
            brightness = (i + 1) * final_brightness / steps
            sequence.append({
                "r": r, 
                "g": g, 
                "b": b, 
                "brightness": brightness, 
                "delay": step_time
            })
        
        return self.set_led_sequence(
            sequence,
            wait_for_completion=wait_for_completion,
            timeout=timeout
        )
