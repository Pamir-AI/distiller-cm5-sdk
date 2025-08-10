#!/usr/bin/env rust-script

use distiller_display_sdk_shared::{
    config, DisplayMode,
    display_init, display_image_raw, display_clear, display_sleep, display_cleanup,
    create_white_image, create_black_image, get_dimensions
};
use std::env;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize logging
    env_logger::init();
    
    println!("=== E-ink Display Test ===");
    
    // Initialize configuration system
    println!("1. Initializing configuration...");
    if let Err(e) = config::initialize_config() {
        println!("Warning: Config initialization failed: {}", e);
        println!("Using default configuration");
    }
    
    // Get current firmware
    match config::get_default_firmware() {
        Ok(firmware) => println!("Current firmware: {}", firmware),
        Err(e) => println!("Error getting firmware: {}", e),
    }
    
    // Check for environment variable override
    if let Ok(firmware_env) = env::var("DISTILLER_EINK_FIRMWARE") {
        println!("Setting firmware from environment: {}", firmware_env);
        if let Err(e) = config::set_default_firmware_from_str(&firmware_env) {
            println!("Error setting firmware: {}", e);
        } else {
            match config::get_default_firmware() {
                Ok(firmware) => println!("Updated firmware: {}", firmware),
                Err(e) => println!("Error getting updated firmware: {}", e),
            }
        }
    }
    
    // Get display dimensions
    println!("\n2. Getting display dimensions...");
    let dimensions = get_dimensions();
    println!("Display dimensions: {}x{} pixels", dimensions.0, dimensions.1);
    
    let array_size = (dimensions.0 * dimensions.1 / 8) as usize;
    println!("Required data size: {} bytes", array_size);
    
    // Test image creation
    println!("\n3. Testing image creation...");
    let white_image = create_white_image();
    let black_image = create_black_image();
    
    println!("White image size: {} bytes", white_image.len());
    println!("Black image size: {} bytes", black_image.len());
    
    if white_image.len() != array_size {
        println!("ERROR: Image size mismatch!");
        println!("Expected: {} bytes, got: {} bytes", array_size, white_image.len());
        return Err("Image size mismatch".into());
    }
    
    // Test display initialization
    println!("\n4. Testing display initialization...");
    match display_init() {
        Ok(()) => {
            println!("✓ Display initialized successfully");
            
            // Test display operations
            println!("\n5. Testing display operations...");
            
            // Display white image
            println!("Displaying white image...");
            if let Err(e) = display_image_raw(&white_image, DisplayMode::Full) {
                println!("Error displaying white image: {}", e);
            } else {
                println!("✓ White image displayed");
            }
            
            std::thread::sleep(std::time::Duration::from_secs(2));
            
            // Display black image
            println!("Displaying black image...");
            if let Err(e) = display_image_raw(&black_image, DisplayMode::Full) {
                println!("Error displaying black image: {}", e);
            } else {
                println!("✓ Black image displayed");
            }
            
            std::thread::sleep(std::time::Duration::from_secs(2));
            
            // Clear display
            println!("Clearing display...");
            if let Err(e) = display_clear() {
                println!("Error clearing display: {}", e);
            } else {
                println!("✓ Display cleared");
            }
            
            // Sleep display
            println!("Putting display to sleep...");
            if let Err(e) = display_sleep() {
                println!("Error putting display to sleep: {}", e);
            } else {
                println!("✓ Display sleeping");
            }
            
            // Cleanup
            println!("Cleaning up...");
            if let Err(e) = display_cleanup() {
                println!("Error during cleanup: {}", e);
            } else {
                println!("✓ Cleanup completed");
            }
            
        }
        Err(e) => {
            println!("✗ Display initialization failed: {}", e);
            println!("This could be due to:");
            println!("  - Hardware not connected");
            println!("  - Insufficient permissions (try with sudo)");
            println!("  - SPI/GPIO devices not available");
            println!("  - Wrong firmware configuration");
            return Err(e.into());
        }
    }
    
    println!("\n=== Test completed successfully ===");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_config_system() {
        // Test firmware type parsing
        assert!(config::FirmwareType::from_str("EPD128x250").is_ok());
        assert!(config::FirmwareType::from_str("EPD240x416").is_ok());
        assert!(config::FirmwareType::from_str("invalid").is_err());
    }
    
    #[test]
    fn test_image_creation() {
        // Test with default firmware
        let white = create_white_image();
        let black = create_black_image();
        
        assert_eq!(white.len(), black.len());
        assert!(white.len() > 0);
        
        // All bytes in white image should be 0xFF
        assert!(white.iter().all(|&b| b == 0xFF));
        
        // All bytes in black image should be 0x00
        assert!(black.iter().all(|&b| b == 0x00));
    }
    
    #[test]
    fn test_dimensions() {
        let dims = get_dimensions();
        assert!(dims.0 > 0);
        assert!(dims.1 > 0);
        
        // Should be one of the supported resolutions
        let supported = [(128, 250), (240, 416)];
        assert!(supported.contains(&dims));
    }
}