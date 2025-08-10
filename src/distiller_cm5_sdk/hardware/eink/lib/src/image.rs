use crate::error::DisplayError;
use crate::firmware::DisplaySpec;
use crate::config;

pub fn convert_png_to_1bit_with_spec(
    filename: &str,
    spec: &DisplaySpec,
) -> Result<Vec<u8>, DisplayError> {
    let image = lodepng::decode32_file(filename)
        .map_err(|e| DisplayError::Png(format!("Failed to decode PNG: {}", e)))?;

    if image.width != spec.width as usize || image.height != spec.height as usize {
        return Err(DisplayError::Png(format!(
            "Invalid image size: {}x{}, expected {}x{}",
            image.width, image.height, spec.width, spec.height
        )));
    }

    let mut output = vec![0u8; spec.array_size()];

    for y in 0..image.height {
        for x in 0..image.width {
            let pixel_idx = y * image.width + x;
            let pixel = image.buffer[pixel_idx];

            // Convert RGBA to grayscale
            let gray = (pixel.r as u16 + pixel.g as u16 + pixel.b as u16) / 3;

            // Convert to 1-bit (threshold at 128)
            let bit_value = if gray > 128 { 1 } else { 0 };

            // Pack into output buffer
            let byte_idx = (y * image.width + x) / 8;
            let bit_idx = (y * image.width + x) % 8;

            if bit_value == 1 {
                output[byte_idx] |= 1 << (7 - bit_idx);
            }
        }
    }

    Ok(output)
}

// Backwards compatibility function using configurable default firmware
pub fn convert_png_to_1bit(filename: &str) -> Result<Vec<u8>, DisplayError> {
    let spec = config::get_default_spec()?;
    convert_png_to_1bit_with_spec(filename, &spec)
}

pub fn get_dimensions_from_spec(spec: &DisplaySpec) -> (u32, u32) {
    (spec.width, spec.height)
}

// Backwards compatibility function using configurable default firmware
pub fn get_dimensions() -> (u32, u32) {
    match config::get_default_spec() {
        Ok(spec) => get_dimensions_from_spec(&spec),
        Err(_) => {
            log::warn!("Failed to get default firmware spec, falling back to EPD128x250");
            (128, 250) // Fallback to original hardcoded values
        }
    }
}

pub fn create_white_image_with_spec(spec: &DisplaySpec) -> Vec<u8> {
    vec![0xFF; spec.array_size()]
}

pub fn create_black_image_with_spec(spec: &DisplaySpec) -> Vec<u8> {
    vec![0x00; spec.array_size()]
}

// Backwards compatibility functions using configurable default firmware
pub fn create_white_image() -> Vec<u8> {
    match config::get_default_spec() {
        Ok(spec) => create_white_image_with_spec(&spec),
        Err(_) => {
            log::warn!("Failed to get default firmware spec, falling back to EPD128x250");
            vec![0xFF; (128 * 250) / 8] // Fallback to original hardcoded size
        }
    }
}

pub fn create_black_image() -> Vec<u8> {
    match config::get_default_spec() {
        Ok(spec) => create_black_image_with_spec(&spec),
        Err(_) => {
            log::warn!("Failed to get default firmware spec, falling back to EPD128x250");
            vec![0x00; (128 * 250) / 8] // Fallback to original hardcoded size
        }
    }
}

