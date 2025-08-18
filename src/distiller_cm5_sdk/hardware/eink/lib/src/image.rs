use crate::config;
use crate::error::DisplayError;
use crate::firmware::DisplaySpec;

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

    // Calculate bytes per row for proper byte alignment
    let bytes_per_row = ((spec.width + 7) / 8) as usize;

    for y in 0..image.height {
        for x in 0..image.width {
            let pixel_idx = y * image.width + x;
            let pixel = image.buffer[pixel_idx];

            // Convert RGBA to grayscale
            let gray = (pixel.r as u16 + pixel.g as u16 + pixel.b as u16) / 3;

            // Convert to 1-bit (threshold at 128)
            let bit_value = if gray > 128 { 1 } else { 0 };

            // Pack into output buffer with row-aware byte alignment
            let byte_idx = y * bytes_per_row + (x / 8);
            let bit_idx = 7 - (x % 8);

            if bit_value == 1 {
                output[byte_idx] |= 1 << bit_idx;
            }
        }
        // Padding bits in the last byte of each row are already 0 from vec![0u8; ...]
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

// Get dimensions using configurable default firmware
pub fn get_dimensions() -> Result<(u32, u32), DisplayError> {
    let spec = config::get_default_spec()?;
    Ok(get_dimensions_from_spec(&spec))
}

pub fn create_white_image_with_spec(spec: &DisplaySpec) -> Vec<u8> {
    vec![0xFF; spec.array_size()]
}

pub fn create_black_image_with_spec(spec: &DisplaySpec) -> Vec<u8> {
    vec![0x00; spec.array_size()]
}

// Create images using configurable default firmware
pub fn create_white_image() -> Result<Vec<u8>, DisplayError> {
    let spec = config::get_default_spec()?;
    Ok(create_white_image_with_spec(&spec))
}

pub fn create_black_image() -> Result<Vec<u8>, DisplayError> {
    let spec = config::get_default_spec()?;
    Ok(create_black_image_with_spec(&spec))
}
