use crate::error::DisplayError;
use crate::firmware::DisplaySpec;
use image::imageops::{self, FilterType};
use image::{DynamicImage, GenericImageView, GrayImage, ImageBuffer, Luma, Rgb};
use std::path::Path;

#[cfg(target_arch = "aarch64")]
use std::arch::aarch64::*;

/// Scaling methods for image conversion
#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ScalingMethod {
    Letterbox = 0,  // Maintain aspect ratio, add black borders
    CropCenter = 1, // Center crop to fill display
    Stretch = 2,    // Stretch to fill display (may distort)
}

/// Dithering methods for 1-bit conversion
#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum DitheringMethod {
    FloydSteinberg = 0, // High quality dithering
    Simple = 1,         // Fast ordered dithering
}

/// Rotation modes for image transformation
#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum RotationMode {
    None = 0,      // No rotation
    Rotate90 = 1,  // 90 degrees clockwise
    Rotate180 = 2, // 180 degrees
    Rotate270 = 3, // 270 degrees clockwise (90 CCW)
}

/// Image processing options
pub struct ProcessingOptions {
    pub scaling: ScalingMethod,
    pub dithering: DitheringMethod,
    pub rotation: RotationMode, // Rotation mode enum
    pub h_flip: bool,           // Flip horizontally
    pub v_flip: bool,           // Flip vertically
    pub crop_x: Option<u32>,    // X position for crop (None = center)
    pub crop_y: Option<u32>,    // Y position for crop (None = center)
}

impl Default for ProcessingOptions {
    fn default() -> Self {
        Self {
            scaling: ScalingMethod::Letterbox,
            dithering: DitheringMethod::FloydSteinberg,
            rotation: RotationMode::None,
            h_flip: false,
            v_flip: false,
            crop_x: None,
            crop_y: None,
        }
    }
}

/// Load an image from any supported format
pub fn load_image_any_format(path: &str) -> Result<DynamicImage, DisplayError> {
    image::open(path).map_err(|e| DisplayError::Png(format!("Failed to load image: {}", e)))
}

/// Process an image with the given options for e-ink display
pub fn process_image_for_display(
    img: DynamicImage,
    spec: &DisplaySpec,
    options: &ProcessingOptions,
) -> Result<Vec<u8>, DisplayError> {
    let mut processed = img;

    // Apply transformations in order: h_flip -> v_flip -> rotation
    if options.h_flip {
        processed = processed.fliph();
    }

    if options.v_flip {
        processed = processed.flipv();
    }

    // Apply rotation based on the rotation mode
    processed = match options.rotation {
        RotationMode::None => processed,
        RotationMode::Rotate90 => processed.rotate90(),
        RotationMode::Rotate180 => processed.rotate180(),
        RotationMode::Rotate270 => processed.rotate270(),
    };

    // Scale the image
    processed = scale_image(processed, spec.width, spec.height, options)?;

    // Convert to 1-bit
    let binary_data = convert_to_1bit(processed, options.dithering)?;

    // Pack into bytes for e-ink display
    pack_1bit_data(&binary_data, spec.width as usize, spec.height as usize)
}

/// Scale image according to the specified method
fn scale_image(
    img: DynamicImage,
    target_width: u32,
    target_height: u32,
    options: &ProcessingOptions,
) -> Result<DynamicImage, DisplayError> {
    let (orig_width, orig_height) = img.dimensions();

    match options.scaling {
        ScalingMethod::Stretch => {
            // Simple stretch to fill display
            Ok(img.resize_exact(target_width, target_height, FilterType::Lanczos3))
        }

        ScalingMethod::CropCenter => {
            // Scale to fill display completely, then crop
            let scale_w = target_width as f32 / orig_width as f32;
            let scale_h = target_height as f32 / orig_height as f32;
            let scale = scale_w.max(scale_h);

            let new_width = (orig_width as f32 * scale) as u32;
            let new_height = (orig_height as f32 * scale) as u32;

            // Resize first
            let scaled = img.resize(new_width, new_height, FilterType::Lanczos3);

            // Calculate crop position
            let left = options.crop_x.unwrap_or((new_width - target_width) / 2);
            let top = options.crop_y.unwrap_or((new_height - target_height) / 2);

            // Ensure crop is within bounds
            let left = left.min(new_width.saturating_sub(target_width));
            let top = top.min(new_height.saturating_sub(target_height));

            Ok(scaled.crop_imm(left, top, target_width, target_height))
        }

        ScalingMethod::Letterbox => {
            // Scale to fit within display, maintaining aspect ratio
            let scale_w = target_width as f32 / orig_width as f32;
            let scale_h = target_height as f32 / orig_height as f32;
            let scale = scale_w.min(scale_h);

            let new_width = (orig_width as f32 * scale) as u32;
            let new_height = (orig_height as f32 * scale) as u32;

            // Resize the image
            let scaled = img.resize(new_width, new_height, FilterType::Lanczos3);

            // Create new image with target dimensions (white background)
            let mut result = DynamicImage::ImageRgb8(ImageBuffer::from_pixel(
                target_width,
                target_height,
                Rgb([255, 255, 255]),
            ));

            // Calculate paste position (center)
            let paste_x = (target_width - new_width) / 2;
            let paste_y = (target_height - new_height) / 2;

            // Overlay the scaled image
            imageops::overlay(&mut result, &scaled, paste_x.into(), paste_y.into());

            Ok(result)
        }
    }
}

/// Bayer matrix for ordered dithering (4x4)
const BAYER_MATRIX_4X4: [[u8; 4]; 4] =
    [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]];

/// NEON-optimized ordered dithering for ARM64
#[cfg(target_arch = "aarch64")]
fn ordered_dither_neon(img: &GrayImage) -> GrayImage {
    let width = img.width() as usize;
    let height = img.height() as usize;
    let mut output = GrayImage::new(width as u32, height as u32);
    let in_data = img.as_raw();
    let out_data = output.as_mut();

    unsafe {
        for y in 0..height {
            let y_mod = y % 4;
            let mut x = 0;

            // Process 16 pixels at a time with NEON
            while x + 16 <= width {
                let ptr = in_data.as_ptr().add(y * width + x);
                let pixels = vld1q_u8(ptr);

                // Create threshold values based on Bayer matrix
                let mut thresholds = [0u8; 16];
                for i in 0..16 {
                    let x_mod = (x + i) % 4;
                    thresholds[i] = BAYER_MATRIX_4X4[y_mod][x_mod] * 16;
                }

                // Load thresholds into NEON register
                let threshold_vec = vld1q_u8(thresholds.as_ptr());

                // Add threshold to pixels and compare with 128
                let adjusted = vqaddq_u8(pixels, threshold_vec);
                let mask = vcgtq_u8(adjusted, vdupq_n_u8(128));

                // Create output: 255 where mask is true, 0 otherwise
                let result = vbslq_u8(mask, vdupq_n_u8(255), vdupq_n_u8(0));

                // Store result
                let out_ptr = out_data.as_mut_ptr().add(y * width + x);
                vst1q_u8(out_ptr, result);

                x += 16;
            }

            // Handle remaining pixels
            while x < width {
                let pixel = in_data[y * width + x];
                let threshold = BAYER_MATRIX_4X4[y_mod][x % 4] * 16;
                let value = if pixel.saturating_add(threshold) > 128 {
                    255
                } else {
                    0
                };
                out_data[y * width + x] = value;
                x += 1;
            }
        }
    }

    output
}

/// Fallback ordered dithering for non-ARM64
#[cfg(not(target_arch = "aarch64"))]
fn ordered_dither_neon(img: &GrayImage) -> GrayImage {
    let width = img.width();
    let height = img.height();

    ImageBuffer::from_fn(width, height, |x, y| {
        let pixel = img.get_pixel(x, y)[0];
        let threshold = BAYER_MATRIX_4X4[(y % 4) as usize][(x % 4) as usize] * 16;
        if pixel.saturating_add(threshold) > 128 {
            Luma([255u8])
        } else {
            Luma([0u8])
        }
    })
}

/// Convert image to 1-bit using specified dithering method
fn convert_to_1bit(img: DynamicImage, method: DitheringMethod) -> Result<GrayImage, DisplayError> {
    // First convert to grayscale
    let gray = img.to_luma8();

    match method {
        DitheringMethod::FloydSteinberg => {
            // Apply Floyd-Steinberg dithering with NEON optimization
            Ok(floyd_steinberg_dither_neon(gray))
        }
        DitheringMethod::Simple => {
            // Use fast ordered dithering with NEON
            Ok(ordered_dither_neon(&gray))
        }
    }
}

/// Floyd-Steinberg dithering with NEON optimization for ARM64
#[cfg(target_arch = "aarch64")]
fn floyd_steinberg_dither_neon(mut img: GrayImage) -> GrayImage {
    let width = img.width() as usize;
    let height = img.height() as usize;
    let data = img.as_mut();

    // Pre-process: Apply contrast boost for crisper output
    // Formula: pixel = ((pixel - 128) * 1.3 + 128).clamp(0, 255)
    for i in 0..data.len() {
        let pixel = data[i] as f32;
        let adjusted = ((pixel - 128.0) * 1.3 + 128.0).clamp(0.0, 255.0);
        data[i] = adjusted as u8;
    }

    unsafe {
        // Lower threshold for bolder output (115 instead of 128)
        let threshold = vdup_n_u8(115);

        for y in 0..height {
            // Serpentine scanning: alternate direction each row
            let reverse_row = y % 2 == 1;

            if !reverse_row {
                // Left to right for even rows
                let mut x = 0;
                while x + 8 <= width {
                    let idx = y * width + x;
                    let ptr = data.as_ptr().add(idx);
                    let pixels = vld1_u8(ptr);

                    // Threshold comparison
                    // Compare with lower threshold (115) for bolder output
                    let mask = vcgt_u8(pixels, threshold);
                    let result = vbsl_u8(mask, vdup_n_u8(255), vdup_n_u8(0));

                    // Store thresholded values
                    let out_ptr = data.as_mut_ptr().add(idx);
                    vst1_u8(out_ptr, result);

                    // Error diffusion (scalar - can't be vectorized easily)
                    // Extract pixels to array first
                    let pixel_array: [u8; 8] = std::mem::transmute(pixels);
                    for i in 0..8 {
                        let pixel_idx = idx + i;
                        let old_pixel = pixel_array[i] as i32;
                        let new_pixel = if old_pixel > 115 { 255 } else { 0 };
                        // Clamp error to prevent excessive accumulation
                        let error = (old_pixel - new_pixel).clamp(-100, 100);

                        // Distribute error to neighboring pixels
                        if x + i + 1 < width {
                            let right_idx = pixel_idx + 1;
                            // Reduced error to right (6/16 instead of 7/16) for crisper edges
                            let new_val = (data[right_idx] as i32 + error * 6 / 16).clamp(0, 255);
                            data[right_idx] = new_val as u8;
                        }

                        if y + 1 < height {
                            if x + i > 0 {
                                let below_left_idx = (y + 1) * width + x + i - 1;
                                // Reduced error to bottom-left (2/16 instead of 3/16)
                                let new_val =
                                    (data[below_left_idx] as i32 + error * 2 / 16).clamp(0, 255);
                                data[below_left_idx] = new_val as u8;
                            }

                            let below_idx = (y + 1) * width + x + i;
                            let new_val = (data[below_idx] as i32 + error * 5 / 16).clamp(0, 255);
                            data[below_idx] = new_val as u8;

                            if x + i + 1 < width {
                                let below_right_idx = (y + 1) * width + x + i + 1;
                                let new_val =
                                    (data[below_right_idx] as i32 + error * 1 / 16).clamp(0, 255);
                                data[below_right_idx] = new_val as u8;
                            }
                        }
                    }

                    x += 8;
                }

                // Handle remaining pixels for forward scan
                while x < width {
                    let idx = y * width + x;
                    let old_pixel = data[idx] as i32;
                    let new_pixel = if old_pixel > 115 { 255 } else { 0 };
                    data[idx] = new_pixel as u8;

                    // Clamp error
                    let error = (old_pixel - new_pixel).clamp(-100, 100);

                    // Distribute error to neighboring pixels
                    if x + 1 < width {
                        let right_idx = idx + 1;
                        // Reduced error to right
                        let new_val = (data[right_idx] as i32 + error * 6 / 16).clamp(0, 255);
                        data[right_idx] = new_val as u8;
                    }

                    if y + 1 < height {
                        if x > 0 {
                            let below_left_idx = (y + 1) * width + x - 1;
                            // Reduced error to bottom-left (2/16 instead of 3/16)
                            let new_val =
                                (data[below_left_idx] as i32 + error * 2 / 16).clamp(0, 255);
                            data[below_left_idx] = new_val as u8;
                        }

                        let below_idx = (y + 1) * width + x;
                        let new_val = (data[below_idx] as i32 + error * 5 / 16).clamp(0, 255);
                        data[below_idx] = new_val as u8;

                        if x + 1 < width {
                            let below_right_idx = (y + 1) * width + x + 1;
                            let new_val =
                                (data[below_right_idx] as i32 + error * 1 / 16).clamp(0, 255);
                            data[below_right_idx] = new_val as u8;
                        }
                    }

                    x += 1;
                }
            } else {
                // Right to left for odd rows (serpentine)
                let mut x = width as i32 - 1;
                while x >= 0 {
                    let idx = y * width + x as usize;
                    let old_pixel = data[idx] as i32;
                    let new_pixel = if old_pixel > 115 { 255 } else { 0 };
                    data[idx] = new_pixel as u8;

                    // Clamp error
                    let error = (old_pixel - new_pixel).clamp(-100, 100);

                    // Distribute error (mirrored for reverse scan)
                    if x > 0 {
                        let left_idx = idx - 1;
                        let new_val = (data[left_idx] as i32 + error * 6 / 16).clamp(0, 255);
                        data[left_idx] = new_val as u8;
                    }

                    if y + 1 < height {
                        if x < width as i32 - 1 {
                            let below_right_idx = (y + 1) * width + x as usize + 1;
                            let new_val =
                                (data[below_right_idx] as i32 + error * 2 / 16).clamp(0, 255);
                            data[below_right_idx] = new_val as u8;
                        }

                        let below_idx = (y + 1) * width + x as usize;
                        let new_val = (data[below_idx] as i32 + error * 5 / 16).clamp(0, 255);
                        data[below_idx] = new_val as u8;

                        if x > 0 {
                            let below_left_idx = (y + 1) * width + x as usize - 1;
                            let new_val =
                                (data[below_left_idx] as i32 + error * 1 / 16).clamp(0, 255);
                            data[below_left_idx] = new_val as u8;
                        }
                    }

                    x -= 1;
                }
            }
        }
    }

    img
}

/// Fallback Floyd-Steinberg for non-ARM64
#[cfg(not(target_arch = "aarch64"))]
fn floyd_steinberg_dither_neon(mut img: GrayImage) -> GrayImage {
    let width = img.width();
    let height = img.height();

    // Pre-process: Apply contrast boost for crisper output
    for y in 0..height {
        for x in 0..width {
            let pixel = img.get_pixel(x, y)[0] as f32;
            let adjusted = ((pixel - 128.0) * 1.3 + 128.0).clamp(0.0, 255.0);
            img.put_pixel(x, y, Luma([adjusted as u8]));
        }
    }

    for y in 0..height {
        // Serpentine scanning
        let reverse_row = y % 2 == 1;

        if !reverse_row {
            // Left to right
            for x in 0..width {
                let old_pixel = img.get_pixel(x, y)[0] as i32;
                let new_pixel = if old_pixel > 115 { 255 } else { 0 };
                img.put_pixel(x, y, Luma([new_pixel as u8]));

                // Clamp error
                let error = (old_pixel - new_pixel).clamp(-100, 100);

                // Distribute error to neighboring pixels
                if x + 1 < width {
                    let pixel = img.get_pixel(x + 1, y)[0] as i32;
                    let new_val = (pixel + error * 6 / 16).clamp(0, 255);
                    img.put_pixel(x + 1, y, Luma([new_val as u8]));
                }

                if y + 1 < height {
                    if x > 0 {
                        let pixel = img.get_pixel(x - 1, y + 1)[0] as i32;
                        let new_val = (pixel + error * 2 / 16).clamp(0, 255);
                        img.put_pixel(x - 1, y + 1, Luma([new_val as u8]));
                    }

                    let pixel = img.get_pixel(x, y + 1)[0] as i32;
                    let new_val = (pixel + error * 5 / 16).clamp(0, 255);
                    img.put_pixel(x, y + 1, Luma([new_val as u8]));

                    if x + 1 < width {
                        let pixel = img.get_pixel(x + 1, y + 1)[0] as i32;
                        let new_val = (pixel + error * 1 / 16).clamp(0, 255);
                        img.put_pixel(x + 1, y + 1, Luma([new_val as u8]));
                    }
                }
            }
        } else {
            // Right to left for odd rows
            for x in (0..width).rev() {
                let old_pixel = img.get_pixel(x, y)[0] as i32;
                let new_pixel = if old_pixel > 115 { 255 } else { 0 };
                img.put_pixel(x, y, Luma([new_pixel as u8]));

                // Clamp error
                let error = (old_pixel - new_pixel).clamp(-100, 100);

                // Distribute error (mirrored for reverse)
                if x > 0 {
                    let pixel = img.get_pixel(x - 1, y)[0] as i32;
                    let new_val = (pixel + error * 6 / 16).clamp(0, 255);
                    img.put_pixel(x - 1, y, Luma([new_val as u8]));
                }

                if y + 1 < height {
                    if x < width - 1 {
                        let pixel = img.get_pixel(x + 1, y + 1)[0] as i32;
                        let new_val = (pixel + error * 2 / 16).clamp(0, 255);
                        img.put_pixel(x + 1, y + 1, Luma([new_val as u8]));
                    }

                    let pixel = img.get_pixel(x, y + 1)[0] as i32;
                    let new_val = (pixel + error * 5 / 16).clamp(0, 255);
                    img.put_pixel(x, y + 1, Luma([new_val as u8]));

                    if x > 0 {
                        let pixel = img.get_pixel(x - 1, y + 1)[0] as i32;
                        let new_val = (pixel + error * 1 / 16).clamp(0, 255);
                        img.put_pixel(x - 1, y + 1, Luma([new_val as u8]));
                    }
                }
            }
        }
    }

    img
}

/// Pack 1-bit image data into byte array for e-ink display with correct NEON optimization
#[cfg(target_arch = "aarch64")]
fn pack_1bit_data(img: &GrayImage, width: usize, height: usize) -> Result<Vec<u8>, DisplayError> {
    // Calculate byte-aligned size for non-byte-aligned widths
    let bytes_per_row = (width + 7) / 8;
    let mut output = vec![0u8; bytes_per_row * height];
    let data = img.as_raw();

    unsafe {
        let threshold = vdup_n_u8(128);
        let mut pixel_idx = 0;
        let mut byte_idx = 0;

        // Process row by row for proper byte alignment
        for y in 0..height {
            let row_start = y * width;
            let row_byte_start = y * bytes_per_row;
            let mut x = 0;

            // Process 8 pixels at a time within the row
            while x + 8 <= width {
                let pixels = vld1_u8(data.as_ptr().add(row_start + x));
                let mask = vcgt_u8(pixels, threshold);

                // Extract mask values and pack MSB-first
                // pixel 0 -> bit 7, pixel 1 -> bit 6, etc.
                let mask_bytes: [u8; 8] = std::mem::transmute(mask);
                let mut byte_val = 0u8;

                for i in 0..8 {
                    if mask_bytes[i] != 0 {
                        byte_val |= 1 << (7 - i); // MSB-first ordering!
                    }
                }

                output[row_byte_start + x / 8] = byte_val;
                x += 8;
            }

            // Handle remaining pixels in the row
            while x < width {
                let pixel = data[row_start + x];
                if pixel > 128 {
                    let byte_idx = row_byte_start + x / 8;
                    let bit_pos = 7 - (x % 8); // MSB-first
                    output[byte_idx] |= 1 << bit_pos;
                }
                x += 1;
            }
            // Padding bits in the last byte of each row are already 0
        }
    }

    Ok(output)
}

/// Fallback pack_1bit_data for non-ARM64
#[cfg(not(target_arch = "aarch64"))]
fn pack_1bit_data(img: &GrayImage, width: usize, height: usize) -> Result<Vec<u8>, DisplayError> {
    // Calculate byte-aligned size for non-byte-aligned widths
    let bytes_per_row = (width + 7) / 8;
    let mut output = vec![0u8; bytes_per_row * height];

    for y in 0..height {
        for x in 0..width {
            let pixel = img.get_pixel(x as u32, y as u32)[0];
            let bit_value = if pixel > 128 { 1 } else { 0 };

            // Calculate byte index with row-aware alignment
            let byte_idx = y * bytes_per_row + x / 8;
            let bit_pos = 7 - (x % 8); // MSB first

            if bit_value == 1 {
                output[byte_idx] |= 1 << bit_pos;
            }
        }
        // Padding bits in the last byte of each row are already 0
    }

    Ok(output)
}

/// Process an image file directly with all options
pub fn process_image_file(
    path: &str,
    spec: &DisplaySpec,
    options: &ProcessingOptions,
) -> Result<Vec<u8>, DisplayError> {
    let img = load_image_any_format(path)?;
    process_image_for_display(img, spec, options)
}

/// Get supported image extensions
pub fn get_supported_extensions() -> Vec<&'static str> {
    vec![
        "png", "jpg", "jpeg", "gif", "bmp", "tiff", "tif", "webp", "ico", "pbm", "pgm", "ppm",
        "pam", "tga", "dds",
    ]
}

/// Check if a file extension is supported
pub fn is_format_supported(path: &str) -> bool {
    if let Some(ext) = Path::new(path).extension() {
        if let Some(ext_str) = ext.to_str() {
            let ext_lower = ext_str.to_lowercase();
            return get_supported_extensions().contains(&ext_lower.as_str());
        }
    }
    false
}
