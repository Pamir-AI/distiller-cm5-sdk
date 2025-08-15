#!/usr/bin/env rust-script

use distiller_display_sdk_shared::{
    config, create_black_image, create_white_image, display_cleanup, display_clear,
    display_image_raw, display_init, display_sleep, get_dimensions,
    image_processing::{
        process_image_file, process_image_for_display, DitheringMethod, ProcessingOptions,
        ScalingMethod,
    },
    DisplayMode,
};
use image::{DynamicImage, ImageBuffer, Luma};
use std::env;
use std::path::Path;

/// Create a checkerboard pattern for testing
fn create_checkerboard_pattern(width: u32, height: u32, square_size: u32) -> DynamicImage {
    let img = ImageBuffer::from_fn(width, height, |x, y| {
        let checker_x = (x / square_size) % 2;
        let checker_y = (y / square_size) % 2;
        if checker_x == checker_y {
            Luma([255u8])
        } else {
            Luma([0u8])
        }
    });
    DynamicImage::ImageLuma8(img)
}

/// Create vertical stripes pattern
fn create_vertical_stripes(width: u32, height: u32, stripe_width: u32) -> DynamicImage {
    let img = ImageBuffer::from_fn(width, height, |x, _y| {
        if (x / stripe_width) % 2 == 0 {
            Luma([255u8])
        } else {
            Luma([0u8])
        }
    });
    DynamicImage::ImageLuma8(img)
}

/// Create horizontal stripes pattern
fn create_horizontal_stripes(width: u32, height: u32, stripe_height: u32) -> DynamicImage {
    let img = ImageBuffer::from_fn(width, height, |_x, y| {
        if (y / stripe_height) % 2 == 0 {
            Luma([255u8])
        } else {
            Luma([0u8])
        }
    });
    DynamicImage::ImageLuma8(img)
}

/// Create a gradient pattern
fn create_gradient_pattern(width: u32, height: u32) -> DynamicImage {
    let img = ImageBuffer::from_fn(width, height, |x, _y| {
        let gray_value = (x * 255 / width) as u8;
        Luma([gray_value])
    });
    DynamicImage::ImageLuma8(img)
}

/// Print hex dump of data for debugging
fn hexdump(data: &[u8], max_bytes: usize) {
    println!("Hex dump (first {} bytes):", max_bytes.min(data.len()));
    for (i, chunk) in data.iter().take(max_bytes).enumerate() {
        if i % 16 == 0 {
            print!("\n{:04x}: ", i);
        }
        print!("{:02x} ", chunk);
    }
    println!("\n");

    // Also show as binary for first 32 bytes to see bit patterns
    println!("Binary representation (first 32 bytes):");
    for (i, byte) in data.iter().take(32).enumerate() {
        if i % 4 == 0 {
            print!("\n{:04x}: ", i);
        }
        print!("{:08b} ", byte);
    }
    println!("\n");
}

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
    println!(
        "Display dimensions: {}x{} pixels",
        dimensions.0, dimensions.1
    );

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
        println!(
            "Expected: {} bytes, got: {} bytes",
            array_size,
            white_image.len()
        );
        return Err("Image size mismatch".into());
    }

    // Test display initialization
    println!("\n4. Testing display initialization...");
    match display_init() {
        Ok(()) => {
            println!("✓ Display initialized successfully");

            // Get display spec for image processing
            let spec = config::get_default_spec()?;
            println!("Using display spec: {}x{}", spec.width, spec.height);

            // Test display operations
            println!("\n5. Testing display operations with patterns...");

            // Test 1: Simple white/black images
            println!("\n--- Test 1: White image ---");
            println!("Displaying white image...");
            println!("Expected: All bytes should be 0xFF");
            hexdump(&white_image, 64);
            if let Err(e) = display_image_raw(&white_image, DisplayMode::Full) {
                println!("Error displaying white image: {}", e);
            } else {
                println!("✓ White image displayed");
            }
            std::thread::sleep(std::time::Duration::from_secs(2));

            println!("\n--- Test 2: Black image ---");
            println!("Displaying black image...");
            println!("Expected: All bytes should be 0x00");
            hexdump(&black_image, 64);
            if let Err(e) = display_image_raw(&black_image, DisplayMode::Full) {
                println!("Error displaying black image: {}", e);
            } else {
                println!("✓ Black image displayed");
            }
            std::thread::sleep(std::time::Duration::from_secs(2));

            // Test 2: Checkerboard pattern
            println!("\n--- Test 3: Checkerboard pattern ---");
            let checkerboard = create_checkerboard_pattern(spec.width, spec.height, 16);
            let options = ProcessingOptions::default();
            let checkerboard_data = process_image_for_display(checkerboard, &spec, &options)?;
            println!("Checkerboard data size: {} bytes", checkerboard_data.len());
            println!("Dithering method: {:?}", options.dithering);
            hexdump(&checkerboard_data, 128);

            println!("Displaying checkerboard pattern...");
            if let Err(e) = display_image_raw(&checkerboard_data, DisplayMode::Full) {
                println!("Error displaying checkerboard: {}", e);
            } else {
                println!("✓ Checkerboard displayed");
            }
            std::thread::sleep(std::time::Duration::from_secs(3));

            // Test 3: Vertical stripes
            println!("\n--- Test 4: Vertical stripes ---");
            let vertical = create_vertical_stripes(spec.width, spec.height, 8);
            let vertical_data = process_image_for_display(vertical, &spec, &options)?;
            println!("Vertical stripes data size: {} bytes", vertical_data.len());
            hexdump(&vertical_data, 128);

            println!("Displaying vertical stripes...");
            if let Err(e) = display_image_raw(&vertical_data, DisplayMode::Full) {
                println!("Error displaying vertical stripes: {}", e);
            } else {
                println!("✓ Vertical stripes displayed");
            }
            std::thread::sleep(std::time::Duration::from_secs(3));

            // Test 4: Horizontal stripes
            println!("\n--- Test 5: Horizontal stripes ---");
            let horizontal = create_horizontal_stripes(spec.width, spec.height, 8);
            let horizontal_data = process_image_for_display(horizontal, &spec, &options)?;
            println!(
                "Horizontal stripes data size: {} bytes",
                horizontal_data.len()
            );
            hexdump(&horizontal_data, 128);

            println!("Displaying horizontal stripes...");
            if let Err(e) = display_image_raw(&horizontal_data, DisplayMode::Full) {
                println!("Error displaying horizontal stripes: {}", e);
            } else {
                println!("✓ Horizontal stripes displayed");
            }
            std::thread::sleep(std::time::Duration::from_secs(3));

            // Test 5: Gradient with dithering
            println!("\n--- Test 6: Gradient with Floyd-Steinberg dithering ---");
            let gradient = create_gradient_pattern(spec.width, spec.height);
            let mut gradient_options = ProcessingOptions::default();
            gradient_options.dithering = DitheringMethod::FloydSteinberg;
            let gradient_data =
                process_image_for_display(gradient.clone(), &spec, &gradient_options)?;
            println!("Gradient data size: {} bytes", gradient_data.len());
            println!("Dithering method: {:?}", gradient_options.dithering);
            hexdump(&gradient_data, 128);

            println!("Displaying gradient with Floyd-Steinberg...");
            if let Err(e) = display_image_raw(&gradient_data, DisplayMode::Full) {
                println!("Error displaying gradient: {}", e);
            } else {
                println!("✓ Gradient displayed");
            }
            std::thread::sleep(std::time::Duration::from_secs(3));

            // Test 6: Gradient with simple thresholding
            println!("\n--- Test 7: Gradient with Simple thresholding ---");
            let mut simple_options = ProcessingOptions::default();
            simple_options.dithering = DitheringMethod::Simple;
            let gradient_simple_data = process_image_for_display(gradient, &spec, &simple_options)?;
            println!(
                "Gradient simple data size: {} bytes",
                gradient_simple_data.len()
            );
            println!("Dithering method: {:?}", simple_options.dithering);
            hexdump(&gradient_simple_data, 128);

            println!("Displaying gradient with Simple thresholding...");
            if let Err(e) = display_image_raw(&gradient_simple_data, DisplayMode::Full) {
                println!("Error displaying gradient simple: {}", e);
            } else {
                println!("✓ Gradient simple displayed");
            }
            std::thread::sleep(std::time::Duration::from_secs(3));

            // Test with a real image file if provided as argument
            let args: Vec<String> = env::args().collect();
            if args.len() > 1 {
                let image_path = &args[1];
                if Path::new(image_path).exists() {
                    println!("\n--- Test 8: Loading image from file: {} ---", image_path);

                    // Test with Floyd-Steinberg, rotated and flipped
                    let mut file_options = ProcessingOptions::default();
                    file_options.dithering = DitheringMethod::FloydSteinberg;
                    file_options.scaling = ScalingMethod::Letterbox;
                    file_options.rotate = true; // Rotate 90 degrees counter-clockwise
                    file_options.flip = true; // Flip horizontally

                    match process_image_file(image_path, &spec, &file_options) {
                        Ok(image_data) => {
                            println!("Image data size: {} bytes", image_data.len());
                            println!("Processing options:");
                            println!("  Dithering: {:?}", file_options.dithering);
                            println!("  Scaling: {:?}", file_options.scaling);
                            println!("  Rotate: {}", file_options.rotate);
                            println!("  Flip: {}", file_options.flip);
                            hexdump(&image_data, 256);

                            println!("Displaying image with Floyd-Steinberg...");
                            if let Err(e) = display_image_raw(&image_data, DisplayMode::Full) {
                                println!("Error displaying image: {}", e);
                            } else {
                                println!("✓ Image displayed with Floyd-Steinberg");
                            }
                            std::thread::sleep(std::time::Duration::from_secs(5));

                            // Also test with Simple (ordered) dithering for comparison
                            println!(
                                "\n--- Test 9: Same image with Simple (ordered) dithering ---"
                            );
                            file_options.dithering = DitheringMethod::Simple;

                            match process_image_file(image_path, &spec, &file_options) {
                                Ok(simple_data) => {
                                    println!("Processing with Simple dithering...");
                                    println!("  Dithering: {:?}", file_options.dithering);
                                    hexdump(&simple_data, 128);

                                    println!("Displaying image with Simple dithering...");
                                    if let Err(e) =
                                        display_image_raw(&simple_data, DisplayMode::Full)
                                    {
                                        println!("Error displaying image: {}", e);
                                    } else {
                                        println!("✓ Image displayed with Simple dithering");
                                    }
                                    std::thread::sleep(std::time::Duration::from_secs(5));
                                }
                                Err(e) => {
                                    println!("Error processing with Simple dithering: {}", e);
                                }
                            }
                        }
                        Err(e) => {
                            println!("Error processing image file: {}", e);
                        }
                    }
                } else {
                    println!("Image file not found: {}", image_path);
                }
            } else {
                println!("\nTip: You can provide an image file as argument to test:");
                println!("  cargo run --bin test_display -- /path/to/image.png");
            }

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

