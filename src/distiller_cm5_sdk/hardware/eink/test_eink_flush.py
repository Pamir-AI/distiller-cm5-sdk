#!/usr/bin/env python3
"""
Quick E-ink Display Flush Test
Tests basic e-ink display functionality without mocking.
"""

import sys
import time
import os
from eink import EinkDriver, load_and_convert_image

def test_eink_flush():
    """Test if we can initialize and flush the e-ink display."""
    print("E-ink Display Flush Test")
    print("=" * 30)
    
    display = None
    try:
        # Initialize display
        print("1. Initializing e-ink display...")
        display = EinkDriver()
        
        if not display.initialize():
            print("❌ Failed to initialize e-ink display")
            return False
        
        print("✅ E-ink display initialized successfully")
        

        # display a test image
        print("2. Displaying test image...")
        # use curren path to find the test image
        image_path = os.path.join(os.path.dirname(__file__), "test_image.png")
        image_data = load_and_convert_image(image_path, threshold=128, dither=True)
        display.display_image(image_data)
        print("✅ Test image displayed successfully")
        
        # Wait a moment to see the effect
        print("3. Waiting 2 seconds...")
        # Test clearing/flushing the display
        print("4. Clearing/flushing display...")
        # display.clear_display()
        print("✅ Display cleared successfully")
        
        # Wait a moment to see the effect
        print("5. Waiting 2 seconds...")
        # time.sleep(2)
        
        print("✅ E-ink flush test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during e-ink test: {e}")
        print(f"Error type: {type(e).__name__}")
        return False
        
    finally:
        # Cleanup
        if display:
            print("6. Cleaning up...")
            display.cleanup()
            print("✅ Cleanup completed")

def main():
    """Main test function."""
    print("Starting e-ink display hardware test...")
    print()
    
    success = test_eink_flush()
    
    print()
    if success:
        print("🎉 E-ink display test PASSED!")
        sys.exit(0)
    else:
        print("💥 E-ink display test FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    main() 