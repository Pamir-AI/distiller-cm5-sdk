use std::ffi::CStr;
use std::os::raw::{c_char, c_int, c_uint};
use std::ptr;

use crate::display;
use crate::firmware::DisplayFirmware;
use crate::protocol::DisplayMode;
use crate::config;
use crate::image_processing::{ProcessingOptions, ScalingMethod, DitheringMethod};

// C FFI exports
#[unsafe(no_mangle)]
pub extern "C" fn display_init() -> c_int {
    match display::display_init() {
        Ok(()) => 1, // true
        Err(e) => {
            log::error!("Display init failed: {}", e);
            0 // false
        }
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn display_image_raw(data: *const u8, mode: c_int) -> c_int {
    if data.is_null() {
        return 0;
    }

    // Use configurable default firmware array size
    let array_size = match config::get_default_spec() {
        Ok(spec) => spec.array_size(),
        Err(_) => {
            log::warn!("Failed to get default firmware spec, falling back to EPD128x250");
            (128 * 250) / 8 // Fallback to original hardcoded size
        }
    };
    let data_slice = unsafe { std::slice::from_raw_parts(data, array_size) };
    let display_mode = match mode {
        0 => DisplayMode::Full,
        1 => DisplayMode::Partial,
        _ => return 0,
    };

    match display::display_image_raw(data_slice, display_mode) {
        Ok(()) => 1,
        Err(e) => {
            log::error!("Display image raw failed: {}", e);
            0
        }
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn display_image_png(filename: *const c_char, mode: c_int) -> c_int {
    if filename.is_null() {
        return 0;
    }

    let filename_str = unsafe {
        match CStr::from_ptr(filename).to_str() {
            Ok(s) => s,
            Err(_) => return 0,
        }
    };

    let display_mode = match mode {
        0 => DisplayMode::Full,
        1 => DisplayMode::Partial,
        _ => return 0,
    };

    match display::display_image_png(filename_str, display_mode) {
        Ok(()) => 1,
        Err(e) => {
            log::error!("Display image PNG failed: {}", e);
            0
        }
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn display_clear() -> c_int {
    match display::display_clear() {
        Ok(()) => 1,
        Err(e) => {
            log::error!("Display clear failed: {}", e);
            0
        }
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn display_sleep() {
    if let Err(e) = display::display_sleep() {
        log::error!("Display sleep failed: {}", e);
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn display_cleanup() {
    if let Err(e) = display::display_cleanup() {
        log::error!("Display cleanup failed: {}", e);
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn display_get_dimensions(width: *mut c_uint, height: *mut c_uint) {
    if !width.is_null() && !height.is_null() {
        let (w, h) = display::display_get_dimensions();
        unsafe {
            *width = w;
            *height = h;
        }
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn convert_png_to_1bit(filename: *const c_char, output_data: *mut u8) -> c_int {
    if filename.is_null() || output_data.is_null() {
        return 0;
    }

    let filename_str = unsafe {
        match CStr::from_ptr(filename).to_str() {
            Ok(s) => s,
            Err(_) => return 0,
        }
    };

    match display::convert_png_to_1bit(filename_str) {
        Ok(data) => {
            unsafe {
                // Use configurable default firmware array size
                let array_size = match config::get_default_spec() {
                    Ok(spec) => spec.array_size(),
                    Err(_) => {
                        log::warn!("Failed to get default firmware spec, falling back to EPD128x250");
                        (128 * 250) / 8 // Fallback to original hardcoded size
                    }
                };
                ptr::copy_nonoverlapping(data.as_ptr(), output_data, array_size);
            }
            1
        }
        Err(e) => {
            log::error!("Convert PNG to 1bit failed: {}", e);
            0
        }
    }
}

// Configuration FFI functions
#[unsafe(no_mangle)]
pub extern "C" fn display_set_firmware(firmware_str: *const c_char) -> c_int {
    if firmware_str.is_null() {
        return 0;
    }

    let firmware_str = unsafe {
        match CStr::from_ptr(firmware_str).to_str() {
            Ok(s) => s,
            Err(_) => return 0,
        }
    };

    match config::set_default_firmware_from_str(firmware_str) {
        Ok(()) => 1,
        Err(e) => {
            log::error!("Failed to set firmware: {}", e);
            0
        }
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn display_get_firmware(firmware_str: *mut c_char, max_len: c_uint) -> c_int {
    if firmware_str.is_null() || max_len == 0 {
        return 0;
    }

    match config::get_default_firmware() {
        Ok(firmware_type) => {
            let firmware_name = firmware_type.as_str();
            let name_bytes = firmware_name.as_bytes();
            
            if name_bytes.len() + 1 > max_len as usize {
                return 0; // Buffer too small
            }

            unsafe {
                ptr::copy_nonoverlapping(name_bytes.as_ptr(), firmware_str as *mut u8, name_bytes.len());
                *firmware_str.add(name_bytes.len()) = 0; // Null terminator
            }
            1
        }
        Err(e) => {
            log::error!("Failed to get firmware: {}", e);
            0
        }
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn display_initialize_config() -> c_int {
    match config::initialize_config() {
        Ok(()) => 1,
        Err(e) => {
            log::error!("Failed to initialize config: {}", e);
            0
        }
    }
}

// New image processing FFI functions
#[unsafe(no_mangle)]
pub extern "C" fn process_image_auto(
    filename: *const c_char,
    output_data: *mut u8,
    scaling: c_int,
    dithering: c_int,
    rotate: c_int,
    flip: c_int,
    crop_x: c_int,
    crop_y: c_int,
) -> c_int {
    if filename.is_null() || output_data.is_null() {
        return 0;
    }

    let filename_str = unsafe {
        match CStr::from_ptr(filename).to_str() {
            Ok(s) => s,
            Err(_) => return 0,
        }
    };

    // Get display spec
    let spec = match config::get_default_spec() {
        Ok(s) => s,
        Err(e) => {
            log::error!("Failed to get display spec: {}", e);
            return 0;
        }
    };

    // Build processing options
    let options = ProcessingOptions {
        scaling: match scaling {
            0 => ScalingMethod::Letterbox,
            1 => ScalingMethod::CropCenter,
            2 => ScalingMethod::Stretch,
            _ => ScalingMethod::Letterbox,
        },
        dithering: match dithering {
            0 => DitheringMethod::FloydSteinberg,
            1 => DitheringMethod::Simple,
            _ => DitheringMethod::FloydSteinberg,
        },
        rotate: rotate != 0,
        flip: flip != 0,
        crop_x: if crop_x < 0 { None } else { Some(crop_x as u32) },
        crop_y: if crop_y < 0 { None } else { Some(crop_y as u32) },
    };

    // Process the image
    match crate::image_processing::process_image_file(filename_str, &spec, &options) {
        Ok(data) => {
            unsafe {
                ptr::copy_nonoverlapping(data.as_ptr(), output_data, spec.array_size());
            }
            1
        }
        Err(e) => {
            log::error!("Image processing failed: {}", e);
            0
        }
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn is_image_format_supported(filename: *const c_char) -> c_int {
    if filename.is_null() {
        return 0;
    }

    let filename_str = unsafe {
        match CStr::from_ptr(filename).to_str() {
            Ok(s) => s,
            Err(_) => return 0,
        }
    };

    if crate::image_processing::is_format_supported(filename_str) {
        1
    } else {
        0
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn get_supported_image_formats(formats: *mut c_char, max_len: c_uint) -> c_int {
    if formats.is_null() || max_len == 0 {
        return 0;
    }

    let extensions = crate::image_processing::get_supported_extensions();
    let formats_str = extensions.join(",");
    let formats_bytes = formats_str.as_bytes();

    if formats_bytes.len() + 1 > max_len as usize {
        return 0; // Buffer too small
    }

    unsafe {
        ptr::copy_nonoverlapping(formats_bytes.as_ptr(), formats as *mut u8, formats_bytes.len());
        *formats.add(formats_bytes.len()) = 0; // Null terminator
    }

    1
}

