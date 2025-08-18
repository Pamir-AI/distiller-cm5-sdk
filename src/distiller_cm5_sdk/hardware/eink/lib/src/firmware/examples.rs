/// Examples of using different firmware variants
/// 
/// This file demonstrates how to use the various firmware configurations
/// for different display modes and variants.

use crate::firmware::{EPD240x416Firmware, EPD122x250Firmware};
use crate::protocol::{create_protocol_with_firmware, DisplayMode};
use crate::display::{GenericDisplay, DisplayDriver};
use crate::error::DisplayError;

/// Example: Using the 240x416 display with 4-gray mode
pub fn example_240x416_4gray() -> Result<(), DisplayError> {
    // Create firmware instance
    let firmware = EPD240x416Firmware::new();
    
    // Create protocol with the firmware
    let mut protocol = create_protocol_with_firmware(firmware)?;
    
    // Initialize with 4-gray mode
    let init_seq = protocol.get_spec(); // Get firmware reference through protocol
    // Note: This is a simplified example. In practice, you'd need to access
    // the firmware's get_4g_init_sequence() method through a custom protocol
    
    // Create display driver
    let mut display = GenericDisplay::new(protocol);
    display.init()?;
    
    // Clear the display
    display.clear()?;
    
    // Clean up
    display.cleanup()?;
    
    Ok(())
}

/// Example: Using the 240x416 display with fast mode
pub fn example_240x416_fast() -> Result<(), DisplayError> {
    let firmware = EPD240x416Firmware::new();
    let protocol = create_protocol_with_firmware(firmware)?;
    let mut display = GenericDisplay::new(protocol);
    
    display.init()?;
    
    // For fast mode, you would typically call the fast init sequence
    // This would require extending the protocol trait or using a custom implementation
    
    display.cleanup()?;
    
    Ok(())
}

/// Example: Switching between firmware variants at compile time
pub fn example_compile_time_switch() -> Result<(), DisplayError> {
    // Switch between different firmware by changing the type
    #[cfg(feature = "epd240x416")]
    type CurrentFirmware = EPD240x416Firmware;
    
    #[cfg(not(feature = "epd240x416"))]
    type CurrentFirmware = EPD122x250Firmware;
    
    let firmware = CurrentFirmware::new();
    let protocol = create_protocol_with_firmware(firmware)?;
    let mut display = GenericDisplay::new(protocol);
    
    display.init()?;
    display.clear()?;
    display.cleanup()?;
    
    Ok(())
}

/// Example: Runtime firmware selection using trait objects
/// Note: This would require additional work to support trait objects
pub fn example_runtime_switch(display_type: &str) -> Result<(), DisplayError> {
    match display_type {
        "240x416" => {
            let firmware = EPD240x416Firmware::new();
            let protocol = create_protocol_with_firmware(firmware)?;
            let mut display = GenericDisplay::new(protocol);
            display.init()?;
            display.cleanup()?;
        }
        "122x250" => {
            let firmware = EPD122x250Firmware::new();
            let protocol = create_protocol_with_firmware(firmware)?;
            let mut display = GenericDisplay::new(protocol);
            display.init()?;
            display.cleanup()?;
        }
        _ => return Err(DisplayError::Png("Unknown display type".to_string())),
    }
    
    Ok(())
}

/// Example: Creating a custom display variant
/// This shows how you would create a new firmware for a different display
pub fn example_custom_firmware() {
    // See the firmware/README.md for detailed instructions on creating
    // custom firmware configurations
    
    // 1. Copy epd240x416.rs to your_display.rs
    // 2. Update the DisplaySpec with your dimensions
    // 3. Modify the register values in the command sequences
    // 4. Add to mod.rs exports
    // 5. Use it like any other firmware:
    
    /*
    let firmware = YourDisplayFirmware::new();
    let protocol = create_protocol_with_firmware(firmware)?;
    let mut display = GenericDisplay::new(protocol);
    */
}