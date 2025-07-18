"""
SAM (System and Microcontroller) Hardware Module

This module provides interfaces to control SAM hardware components including:
- RGB LED control with animation modes, triggers, and brightness control

The module wraps the Linux sysfs interface for the SAM driver.
"""

from .led import LED, LEDError, create_led_with_sudo

__all__ = ['LED', 'LEDError', 'create_led_with_sudo']

# Version information
__version__ = '2.0.0'

# Module metadata
__author__ = 'Distiller CM5 SDK Team'
__description__ = 'SAM hardware control module with sysfs-based RGB LED support'
