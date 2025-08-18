pub mod config;
pub mod display;
pub mod error;
pub mod ffi;
pub mod firmware;
pub mod hardware;
pub mod image;
pub mod image_processing;
pub mod protocol;

// Re-export public API
pub use config::{
    FirmwareType, get_default_firmware, initialize_config, set_default_firmware,
    set_default_firmware_from_str,
};
pub use display::{DefaultDisplay, DisplayDriver, GenericDisplay};
pub use error::DisplayError;
pub use firmware::{Command, CommandSequence, DisplayFirmware, DisplaySpec};
pub use hardware::{DefaultHardwareInterface, GpioController, HardwareInterface, SpiController};
pub use image::{convert_image_to_1bit, create_black_image, create_white_image, get_dimensions};
pub use protocol::{DisplayMode, EinkProtocol};

// Re-export the main functions for backwards compatibility
pub use display::{
    display_cleanup, display_clear, display_get_dimensions, display_image_file, display_image_raw,
    display_init, display_sleep,
};

// C FFI is automatically available through the ffi module
