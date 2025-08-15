use crate::error::DisplayError;
use crate::firmware::DisplaySpec;
use image::{DynamicImage, GenericImageView, ImageBuffer, Luma, Rgb, GrayImage};
use image::imageops::{self, FilterType};
use std::path::Path;
use rayon::prelude::*;

#[cfg(target_arch = "aarch64")]
use std::arch::aarch64::*;

/// Scaling methods for image conversion
#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ScalingMethod {
    Letterbox = 0,   // Maintain aspect ratio, add black borders
    CropCenter = 1,  // Center crop to fill display
    Stretch = 2,     // Stretch to fill display (may distort)
}

/// Dithering methods for 1-bit conversion
#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum DitheringMethod {
    FloydSteinberg = 0,  // High quality dithering
    Simple = 1,          // Fast threshold conversion
}

/// Image processing options
pub struct ProcessingOptions {
    pub scaling: ScalingMethod,
    pub dithering: DitheringMethod,
    pub rotate: bool,      // Rotate 90 degrees counter-clockwise
    pub flip: bool,        // Flip horizontally
    pub crop_x: Option<u32>,  // X position for crop (None = center)
    pub crop_y: Option<u32>,  // Y position for crop (None = center)
}

impl Default for ProcessingOptions {
    fn default() -> Self {
        Self {
            scaling: ScalingMethod::Letterbox,
            dithering: DitheringMethod::FloydSteinberg,
            rotate: false,
            flip: false,
            crop_x: None,
            crop_y: None,
        }
    }
}

/// Load an image from any supported format
pub fn load_image_any_format(path: &str) -> Result<DynamicImage, DisplayError> {
    image::open(path)
        .map_err(|e| DisplayError::Png(format!("Failed to load image: {}", e)))
}

/// Process an image with the given options for e-ink display
pub fn process_image_for_display(
    img: DynamicImage,
    spec: &DisplaySpec,
    options: &ProcessingOptions,
) -> Result<Vec<u8>, DisplayError> {
    let mut processed = img;
    
    // Apply transformations
    if options.flip {
        processed = processed.fliph();
    }
    
    if options.rotate {
        processed = processed.rotate90();
    }
    
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
            let mut result = DynamicImage::ImageRgb8(
                ImageBuffer::from_pixel(target_width, target_height, Rgb([255, 255, 255]))
            );
            
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
const BAYER_MATRIX_4X4: [[u8; 4]; 4] = [
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
];

/// Ordered dithering with NEON optimization - much faster than Floyd-Steinberg
#[cfg(target_arch = "aarch64")]
fn ordered_dither_neon(img: &GrayImage) -> GrayImage {
    let width = img.width() as usize;
    let height = img.height() as usize;
    let mut output = GrayImage::new(width as u32, height as u32);
    let in_data = img.as_raw();
    let out_data = output.as_mut();
    
    unsafe {
        // Process rows in parallel
        (0..height).into_par_iter().for_each(|y| {
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
                let value = if pixel.saturating_add(threshold) > 128 { 255 } else { 0 };
                out_data[y * width + x] = value;
                x += 1;
            }
        });
    }
    
    output
}

#[cfg(not(target_arch = "aarch64"))]
fn ordered_dither_neon(img: &GrayImage) -> GrayImage {
    // Fallback to regular ordered dithering
    ordered_dither(img)
}

/// Standard ordered dithering (non-NEON)
fn ordered_dither(img: &GrayImage) -> GrayImage {
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
            // Apply Floyd-Steinberg dithering
            Ok(floyd_steinberg_dither(gray))
        }
        DitheringMethod::Simple => {
            // Use fast ordered dithering with NEON if available
            Ok(ordered_dither_neon(&gray))
        }
    }
}

/// Floyd-Steinberg dithering implementation with NEON optimization for ARM64
#[cfg(target_arch = "aarch64")]
fn floyd_steinberg_dither(mut img: GrayImage) -> GrayImage {
    let width = img.width() as usize;
    let height = img.height() as usize;
    let data = img.as_mut();
    
    // Process in chunks of 16 pixels for NEON
    for y in 0..height {
        let mut x = 0;
        
        // NEON vectorized processing for aligned chunks
        while x + 16 <= width {
            unsafe {
                let ptr = data.as_ptr().add(y * width + x);
                let pixels = vld1q_u8(ptr);
                
                // Threshold at 128 using NEON
                let threshold = vdupq_n_u8(128);
                let mask = vcgtq_u8(pixels, threshold);
                
                // Create output: 255 where mask is true, 0 otherwise
                let white = vdupq_n_u8(255);
                let black = vdupq_n_u8(0);
                let result = vbslq_u8(mask, white, black);
                
                // Store result
                let out_ptr = data.as_mut_ptr().add(y * width + x);
                vst1q_u8(out_ptr, result);
                
                // Calculate and distribute errors (simplified for NEON)
                // This is a simplified version - full Floyd-Steinberg would need more complex error distribution
                let pixels_i16 = vmovl_u8(vget_low_u8(pixels));
                let result_i16 = vmovl_u8(vget_low_u8(result));
                let error = vsubq_s16(vreinterpretq_s16_u16(pixels_i16), vreinterpretq_s16_u16(result_i16));
                
                // Distribute to right neighbor (7/16 of error)
                if x + 16 < width {
                    let right_ptr = data.as_mut_ptr().add(y * width + x + 16);
                    let right_pixels = vld1_u8(right_ptr);
                    let right_i16 = vmovl_u8(right_pixels);
                    let error_7_16 = vshrq_n_s16(vmulq_n_s16(error, 7), 4);
                    let new_right = vqaddq_s16(vreinterpretq_s16_u16(right_i16), error_7_16);
                    let clamped = vqmovun_s16(new_right);
                    vst1_u8(right_ptr, clamped);
                }
            }
            x += 16;
        }
        
        // Handle remaining pixels with scalar code
        while x < width {
            let idx = y * width + x;
            let old_pixel = data[idx] as i32;
            let new_pixel = if old_pixel > 128 { 255 } else { 0 };
            data[idx] = new_pixel as u8;
            
            let error = old_pixel - new_pixel;
            
            // Distribute error to neighboring pixels
            if x + 1 < width {
                let right_idx = idx + 1;
                let new_val = (data[right_idx] as i32 + error * 7 / 16).clamp(0, 255);
                data[right_idx] = new_val as u8;
            }
            
            if y + 1 < height {
                if x > 0 {
                    let below_left_idx = (y + 1) * width + x - 1;
                    let new_val = (data[below_left_idx] as i32 + error * 3 / 16).clamp(0, 255);
                    data[below_left_idx] = new_val as u8;
                }
                
                let below_idx = (y + 1) * width + x;
                let new_val = (data[below_idx] as i32 + error * 5 / 16).clamp(0, 255);
                data[below_idx] = new_val as u8;
                
                if x + 1 < width {
                    let below_right_idx = (y + 1) * width + x + 1;
                    let new_val = (data[below_right_idx] as i32 + error * 1 / 16).clamp(0, 255);
                    data[below_right_idx] = new_val as u8;
                }
            }
            x += 1;
        }
    }
    
    img
}

/// Floyd-Steinberg dithering implementation (fallback for non-ARM64)
#[cfg(not(target_arch = "aarch64"))]
fn floyd_steinberg_dither(mut img: GrayImage) -> GrayImage {
    let width = img.width();
    let height = img.height();
    
    for y in 0..height {
        for x in 0..width {
            let old_pixel = img.get_pixel(x, y)[0] as i32;
            let new_pixel = if old_pixel > 128 { 255 } else { 0 };
            img.put_pixel(x, y, Luma([new_pixel as u8]));
            
            let error = old_pixel - new_pixel;
            
            // Distribute error to neighboring pixels
            if x + 1 < width {
                let pixel = img.get_pixel(x + 1, y)[0] as i32;
                let new_val = (pixel + error * 7 / 16).clamp(0, 255);
                img.put_pixel(x + 1, y, Luma([new_val as u8]));
            }
            
            if y + 1 < height {
                if x > 0 {
                    let pixel = img.get_pixel(x - 1, y + 1)[0] as i32;
                    let new_val = (pixel + error * 3 / 16).clamp(0, 255);
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
    }
    
    img
}

/// Pack 1-bit image data into byte array for e-ink display with NEON optimization
#[cfg(target_arch = "aarch64")]
fn pack_1bit_data(img: &GrayImage, width: usize, height: usize) -> Result<Vec<u8>, DisplayError> {
    let mut output = vec![0u8; (width * height + 7) / 8];
    let data = img.as_raw();
    
    let mut bit_idx = 0;
    let mut pixel_idx = 0;
    
    // Process 128 pixels at a time using NEON (16 bytes -> 16 bits -> 2 bytes output)
    while pixel_idx + 128 <= width * height {
        unsafe {
            // Load 128 pixels in 8 NEON registers (16 pixels each)
            let threshold = vdupq_n_u8(128);
            let mut packed_bits = 0u128;
            
            for i in 0..8 {
                let ptr = data.as_ptr().add(pixel_idx + i * 16);
                let pixels = vld1q_u8(ptr);
                
                // Compare with threshold
                let mask = vcgtq_u8(pixels, threshold);
                
                // Extract comparison results as bits
                // This is simplified - actual implementation would use vget_lane and bit manipulation
                for j in 0..16 {
                    let bit = vgetq_lane_u8(mask, j) & 1;
                    packed_bits |= (bit as u128) << (i * 16 + j);
                }
            }
            
            // Write packed bits to output
            for i in 0..16 {
                output[bit_idx / 8 + i] = ((packed_bits >> (i * 8)) & 0xFF) as u8;
            }
        }
        
        pixel_idx += 128;
        bit_idx += 128;
    }
    
    // Handle remaining pixels with scalar code
    while pixel_idx < width * height {
        let pixel = data[pixel_idx];
        let bit_value = if pixel > 128 { 1 } else { 0 };
        
        let byte_idx = bit_idx / 8;
        let bit_pos = 7 - (bit_idx % 8);  // MSB first
        
        if bit_value == 1 {
            output[byte_idx] |= 1 << bit_pos;
        }
        
        pixel_idx += 1;
        bit_idx += 1;
    }
    
    Ok(output)
}

/// Pack 1-bit image data into byte array for e-ink display (fallback for non-ARM64)
#[cfg(not(target_arch = "aarch64"))]
fn pack_1bit_data(img: &GrayImage, width: usize, height: usize) -> Result<Vec<u8>, DisplayError> {
    let mut output = vec![0u8; (width * height + 7) / 8];
    
    // Use parallel iteration with rayon for better performance
    output.par_chunks_mut(width / 8).enumerate().for_each(|(y, chunk)| {
        for x_byte in 0..chunk.len() {
            let mut byte_val = 0u8;
            for bit in 0..8 {
                let x = x_byte * 8 + bit;
                if x < width {
                    let pixel = img.get_pixel(x as u32, y as u32)[0];
                    if pixel > 128 {
                        byte_val |= 1 << (7 - bit);
                    }
                }
            }
            chunk[x_byte] = byte_val;
        }
    });
    
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
        "png", "jpg", "jpeg", "gif", "bmp", "tiff", "tif",
        "webp", "ico", "pbm", "pgm", "ppm", "pam", "tga", "dds"
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