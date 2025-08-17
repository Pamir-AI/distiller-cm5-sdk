use crate::error::DisplayError;
use crate::firmware::{DisplayFirmware, DisplaySpec, EPD128x250Firmware, EPD240x416Firmware};
use std::sync::{Mutex, OnceLock};

/// Supported firmware types
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FirmwareType {
    EPD128x250,
    EPD240x416,
}

impl FirmwareType {
    /// Create a firmware instance for this type
    pub fn create_firmware(&self) -> Box<dyn DisplayFirmware> {
        match self {
            FirmwareType::EPD128x250 => Box::new(EPD128x250Firmware::new()),
            FirmwareType::EPD240x416 => Box::new(EPD240x416Firmware::new()),
        }
    }

    /// Get the display spec for this firmware type
    pub fn get_spec(&self) -> DisplaySpec {
        self.create_firmware().get_spec().clone()
    }

    /// Parse firmware type from string
    pub fn from_str(s: &str) -> Result<Self, DisplayError> {
        match s.to_lowercase().as_str() {
            "epd128x250" | "128x250" => Ok(FirmwareType::EPD128x250),
            "epd240x416" | "240x416" => Ok(FirmwareType::EPD240x416),
            _ => Err(DisplayError::Config(format!(
                "Unknown firmware type: {}. Supported types: EPD128x250, EPD240x416",
                s
            ))),
        }
    }

    /// Get string representation
    pub fn as_str(&self) -> &'static str {
        match self {
            FirmwareType::EPD128x250 => "EPD128x250",
            FirmwareType::EPD240x416 => "EPD240x416",
        }
    }
}

impl std::fmt::Display for FirmwareType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

/// Global configuration for the display system
#[derive(Debug, Clone)]
pub struct DisplayConfig {
    pub default_firmware: FirmwareType,
}

impl DisplayConfig {
    /// Create a new config without defaults - configuration must be provided
    fn new_required() -> Result<Self, DisplayError> {
        // Try environment variable first
        if let Ok(firmware_env) = std::env::var("DISTILLER_EINK_FIRMWARE") {
            let firmware_type = FirmwareType::from_str(&firmware_env)?;
            return Ok(Self {
                default_firmware: firmware_type,
            });
        }

        // Try config file
        let config_paths = ["/opt/distiller-cm5-sdk/eink.conf", "./eink.conf"];

        for path in &config_paths {
            if let Ok(content) = std::fs::read_to_string(path) {
                for line in content.lines() {
                    let line = line.trim();
                    if line.starts_with("firmware=") || line.starts_with("FIRMWARE=") {
                        let firmware_str = line.split('=').nth(1).unwrap_or("").trim();
                        if !firmware_str.is_empty() {
                            let firmware_type = FirmwareType::from_str(firmware_str)?;
                            return Ok(Self {
                                default_firmware: firmware_type,
                            });
                        }
                    }
                }
            }
        }

        // No configuration found - fail
        Err(DisplayError::Config(
            "E-ink display configuration not found. \
            Set DISTILLER_EINK_FIRMWARE environment variable to 'EPD128x250' or 'EPD240x416', \
            or create /opt/distiller-cm5-sdk/eink.conf with 'firmware=EPD128x250' or 'firmware=EPD240x416'".to_string()
        ))
    }
}

/// Global configuration instance
static CONFIG: OnceLock<Mutex<DisplayConfig>> = OnceLock::new();

/// Initialize the global configuration
pub fn init_config() -> Result<&'static Mutex<DisplayConfig>, DisplayError> {
    if let Some(config) = CONFIG.get() {
        return Ok(config);
    }

    // Try to create config with required values
    let config = DisplayConfig::new_required()?;
    CONFIG.set(Mutex::new(config)).map_err(|_| {
        DisplayError::Config("Failed to initialize global configuration".to_string())
    })?;

    Ok(CONFIG.get().unwrap())
}

/// Set the default firmware type globally
pub fn set_default_firmware(firmware_type: FirmwareType) -> Result<(), DisplayError> {
    let config = init_config()?;
    let mut config_guard = config
        .lock()
        .map_err(|e| DisplayError::Config(format!("Failed to acquire config lock: {}", e)))?;

    log::info!("Setting default firmware to: {}", firmware_type);
    config_guard.default_firmware = firmware_type;
    Ok(())
}

/// Set the default firmware type from string
pub fn set_default_firmware_from_str(firmware_str: &str) -> Result<(), DisplayError> {
    let firmware_type = FirmwareType::from_str(firmware_str)?;
    set_default_firmware(firmware_type)
}

/// Get the current default firmware type
pub fn get_default_firmware() -> Result<FirmwareType, DisplayError> {
    let config = init_config()?;
    let config_guard = config
        .lock()
        .map_err(|e| DisplayError::Config(format!("Failed to acquire config lock: {}", e)))?;
    Ok(config_guard.default_firmware)
}

/// Create a firmware instance using the default firmware type
pub fn create_default_firmware() -> Result<Box<dyn DisplayFirmware>, DisplayError> {
    let firmware_type = get_default_firmware()?;
    Ok(firmware_type.create_firmware())
}

/// Get the display spec for the default firmware
pub fn get_default_spec() -> Result<DisplaySpec, DisplayError> {
    let firmware_type = get_default_firmware()?;
    Ok(firmware_type.get_spec())
}

// Note: init_from_env and init_from_file removed - configuration is now handled in DisplayConfig::new_required()

/// Initialize configuration from all sources (environment, file)
pub fn initialize_config() -> Result<(), DisplayError> {
    // This will try to load from environment and file automatically
    init_config()?;

    let firmware_type = get_default_firmware()?;
    log::info!(
        "Display configuration initialized with firmware: {}",
        firmware_type
    );

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_firmware_type_parsing() {
        assert_eq!(
            FirmwareType::from_str("EPD128x250").unwrap(),
            FirmwareType::EPD128x250
        );
        assert_eq!(
            FirmwareType::from_str("128x250").unwrap(),
            FirmwareType::EPD128x250
        );
        assert_eq!(
            FirmwareType::from_str("EPD240x416").unwrap(),
            FirmwareType::EPD240x416
        );
        assert_eq!(
            FirmwareType::from_str("240x416").unwrap(),
            FirmwareType::EPD240x416
        );
        assert!(FirmwareType::from_str("invalid").is_err());
    }

    #[test]
    fn test_config_requires_configuration() {
        // Without environment variable or config file, new_required should fail
        std::env::remove_var("DISTILLER_EINK_FIRMWARE");
        let result = DisplayConfig::new_required();
        assert!(result.is_err());
        assert!(
            result
                .unwrap_err()
                .to_string()
                .contains("configuration not found")
        );
    }

    #[test]
    fn test_config_from_env() {
        std::env::set_var("DISTILLER_EINK_FIRMWARE", "EPD240x416");
        let config = DisplayConfig::new_required().unwrap();
        assert_eq!(config.default_firmware, FirmwareType::EPD240x416);
        std::env::remove_var("DISTILLER_EINK_FIRMWARE");
    }

    #[test]
    fn test_set_get_firmware() {
        // Set env var for the test
        std::env::set_var("DISTILLER_EINK_FIRMWARE", "EPD128x250");

        // Initialize and test setting/getting
        initialize_config().unwrap();
        set_default_firmware(FirmwareType::EPD240x416).unwrap();
        assert_eq!(get_default_firmware().unwrap(), FirmwareType::EPD240x416);

        // Reset
        set_default_firmware(FirmwareType::EPD128x250).unwrap();
        assert_eq!(get_default_firmware().unwrap(), FirmwareType::EPD128x250);

        std::env::remove_var("DISTILLER_EINK_FIRMWARE");
    }
}
