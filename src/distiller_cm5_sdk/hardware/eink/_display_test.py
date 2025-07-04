#!/usr/bin/env python3
"""
Display module unit tests for CM5 SDK.
"""

import unittest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock

from display import Display, DisplayError, DisplayMode, display_png, clear_display, get_display_info


class TestDisplay(unittest.TestCase):
    """Test cases for Display class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the library loading to avoid hardware dependencies
        self.mock_lib = Mock()
        self.mock_lib.display_init.return_value = True
        self.mock_lib.display_clear.return_value = True
        self.mock_lib.display_image_png.return_value = True
        self.mock_lib.display_image_raw.return_value = True
        self.mock_lib.convert_png_to_1bit.return_value = True
        self.mock_lib.display_cleanup.return_value = None
        self.mock_lib.display_sleep.return_value = None
        
        # Mock dimensions - return void, but we'll override the method
        self.mock_lib.display_get_dimensions.return_value = None
    
    @patch('ctypes.CDLL')
    @patch('os.path.exists')
    def test_display_initialization(self, mock_exists, mock_cdll):
        """Test display initialization."""
        mock_exists.return_value = True
        mock_cdll.return_value = self.mock_lib
        
        display = Display(auto_init=True)
        
        self.assertTrue(display.is_initialized())
        self.mock_lib.display_init.assert_called_once()
    
    @patch('ctypes.CDLL')
    @patch('os.path.exists')
    def test_display_clear(self, mock_exists, mock_cdll):
        """Test display clear functionality."""
        mock_exists.return_value = True
        mock_cdll.return_value = self.mock_lib
        
        display = Display(auto_init=True)
        display.clear()
        
        self.mock_lib.display_clear.assert_called_once()
    
    @patch('ctypes.CDLL')
    @patch('os.path.exists')
    def test_display_png(self, mock_exists, mock_cdll):
        """Test PNG display functionality."""
        mock_exists.return_value = True
        mock_cdll.return_value = self.mock_lib
        
        # Create a temporary PNG file path
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            display = Display(auto_init=True)
            display.display_image(tmp_path, DisplayMode.FULL)
            
            self.mock_lib.display_image_png.assert_called_once()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    @patch('ctypes.CDLL')
    @patch('os.path.exists')
    def test_display_raw_data(self, mock_exists, mock_cdll):
        """Test raw data display functionality."""
        mock_exists.return_value = True
        mock_cdll.return_value = self.mock_lib
        
        display = Display(auto_init=True)
        
        # Create test data of correct size (4000 bytes)
        test_data = bytes([0xFF] * Display.ARRAY_SIZE)
        display.display_image(test_data, DisplayMode.PARTIAL)
        
        self.mock_lib.display_image_raw.assert_called_once()
    
    @patch('ctypes.CDLL')
    @patch('os.path.exists')
    def test_context_manager(self, mock_exists, mock_cdll):
        """Test context manager functionality."""
        mock_exists.return_value = True
        mock_cdll.return_value = self.mock_lib
        
        with Display(auto_init=False) as display:
            self.assertTrue(display.is_initialized())
        
        self.mock_lib.display_cleanup.assert_called_once()
    
    @patch('ctypes.CDLL')
    @patch('os.path.exists')
    def test_get_dimensions(self, mock_exists, mock_cdll):
        """Test getting display dimensions."""
        mock_exists.return_value = True
        mock_cdll.return_value = self.mock_lib
        
        # Mock the get_dimensions function with proper ctypes behavior
        def mock_get_dimensions(width_ref, height_ref):
            # Simulate setting the values through ctypes references
            width_ref._obj.value = 128
            height_ref._obj.value = 250
        
        self.mock_lib.display_get_dimensions.side_effect = mock_get_dimensions
        
        display = Display(auto_init=True)
        width, height = display.get_dimensions()
        
        self.assertEqual(width, 128)
        self.assertEqual(height, 250)
    
    def test_display_constants(self):
        """Test display constants."""
        self.assertEqual(Display.WIDTH, 128)
        self.assertEqual(Display.HEIGHT, 250)
        self.assertEqual(Display.ARRAY_SIZE, 4000)  # (128 * 250) / 8
    
    def test_display_modes(self):
        """Test display mode enum."""
        self.assertEqual(DisplayMode.FULL, 0)
        self.assertEqual(DisplayMode.PARTIAL, 1)
    
    def test_convenience_functions(self):
        """Test convenience functions."""
        info = get_display_info()
        
        self.assertIn('width', info)
        self.assertIn('height', info)
        self.assertIn('data_size', info)
        self.assertEqual(info['width'], 128)
        self.assertEqual(info['height'], 250)
        self.assertEqual(info['data_size'], 4000)


def run_display_tests():
    """Main function to run display tests."""
    unittest.main(verbosity=2)


if __name__ == '__main__':
    run_display_tests() 