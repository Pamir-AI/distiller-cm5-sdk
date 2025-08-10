use crate::error::DisplayError;
use crate::firmware::DisplaySpec;
use image::{DynamicImage, GenericImageView, ImageBuffer, Luma, Rgb, RgbImage, GrayImage};
use image::imageops::{self, FilterType};
use std::path::Path;

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
            // Simple threshold at 128
            Ok(ImageBuffer::from_fn(gray.width(), gray.height(), |x, y| {
                let pixel = gray.get_pixel(x, y)[0];
                if pixel > 128 {
                    Luma([255u8])
                } else {
                    Luma([0u8])
                }
            }))
        }
    }
}

/// Floyd-Steinberg dithering implementation
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

/// Pack 1-bit image data into byte array for e-ink display
fn pack_1bit_data(img: &GrayImage, width: usize, height: usize) -> Result<Vec<u8>, DisplayError> {
    let mut output = vec![0u8; (width * height + 7) / 8];
    
    for y in 0..height {
        for x in 0..width {
            let pixel = img.get_pixel(x as u32, y as u32)[0];
            let bit_value = if pixel > 128 { 1 } else { 0 };
            
            let bit_idx = y * width + x;
            let byte_idx = bit_idx / 8;
            let bit_pos = 7 - (bit_idx % 8);  // MSB first
            
            if bit_value == 1 {
                output[byte_idx] |= 1 << bit_pos;
            }
        }
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