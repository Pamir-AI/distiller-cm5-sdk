use crate::error::DisplayError;
use crate::firmware::{Command, CommandSequence, DisplayFirmware};
use crate::hardware::{GpioController, HardwareInterface, SpiController, delay_ms, delay_us};

// Display modes
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub enum DisplayMode {
    Full = 0,    // Full refresh (slow, high quality)
    Partial = 1, // Partial refresh (fast, good quality)
}

// E-ink display protocol trait
pub trait EinkProtocol {
    fn init_hardware(&mut self) -> Result<(), DisplayError>;
    fn init_partial(&mut self) -> Result<(), DisplayError>;
    fn write_cmd(&mut self, cmd: u8) -> Result<(), DisplayError>;
    fn write_data(&mut self, data: u8) -> Result<(), DisplayError>;
    fn write_image_data(&mut self, data: &[u8]) -> Result<(), DisplayError>;
    fn check_status(&mut self) -> Result<(), DisplayError>;
    fn update_display(&mut self, mode: DisplayMode) -> Result<(), DisplayError>;
    fn sleep(&mut self) -> Result<(), DisplayError>;
    fn get_spec(&self) -> &crate::firmware::DisplaySpec;
    fn get_write_ram_command(&self) -> u8;
}

// Generic E-ink protocol implementation using firmware abstraction
pub struct GenericEinkProtocol<G: GpioController, S: SpiController, F: DisplayFirmware> {
    hardware: HardwareInterface<G, S>,
    firmware: F,
}

impl<G: GpioController, S: SpiController, F: DisplayFirmware> GenericEinkProtocol<G, S, F> {
    pub fn new(hardware: HardwareInterface<G, S>, firmware: F) -> Self {
        Self { hardware, firmware }
    }

    /// Execute a command sequence
    fn execute_sequence(&mut self, sequence: CommandSequence) -> Result<(), DisplayError> {
        for command in sequence.commands {
            match command {
                Command::WriteCommand(cmd) => self.write_cmd(cmd)?,
                Command::WriteData(data) => self.write_data(data)?,
                Command::Delay(ms) => delay_ms(ms),
                Command::CheckStatus => self.check_status()?,
                Command::Reset => {
                    self.hardware.write_rst(false)?;
                    delay_ms(10);
                    self.hardware.write_rst(true)?;
                    delay_ms(10);
                }
            }
        }
        Ok(())
    }
}

impl<G: GpioController, S: SpiController, F: DisplayFirmware> EinkProtocol
    for GenericEinkProtocol<G, S, F>
{
    fn init_hardware(&mut self) -> Result<(), DisplayError> {
        // Execute reset sequence first
        let reset_sequence = self.firmware.get_reset_sequence();
        self.execute_sequence(reset_sequence)?;

        // Execute main initialization sequence
        let init_sequence = self.firmware.get_init_sequence();
        self.execute_sequence(init_sequence)?;

        Ok(())
    }

    fn init_partial(&mut self) -> Result<(), DisplayError> {
        let partial_sequence = self.firmware.get_partial_init_sequence();
        self.execute_sequence(partial_sequence)?;
        Ok(())
    }

    fn write_cmd(&mut self, cmd: u8) -> Result<(), DisplayError> {
        delay_us(10);
        self.hardware.write_dc(false)?;
        self.hardware.spi_write_all(&[cmd])?;
        Ok(())
    }

    fn write_data(&mut self, data: u8) -> Result<(), DisplayError> {
        delay_us(10);
        self.hardware.write_dc(true)?;
        self.hardware.spi_write_all(&[data])?;
        Ok(())
    }

    fn write_image_data(&mut self, data: &[u8]) -> Result<(), DisplayError> {
        // Validate image size using firmware
        self.firmware.validate_image_size(data)?;

        self.hardware.write_dc(true)?;
        self.hardware.spi_write_all(data)?;
        Ok(())
    }

    fn check_status(&mut self) -> Result<(), DisplayError> {
        let mut watchdog_counter = 0;
        while self.hardware.read_busy()? && watchdog_counter < 1000 {
            delay_ms(10);
            watchdog_counter += 1;
        }

        if watchdog_counter >= 1000 {
            log::warn!("Display busy timeout");
            return Err(DisplayError::Timeout);
        }

        Ok(())
    }

    fn update_display(&mut self, mode: DisplayMode) -> Result<(), DisplayError> {
        let is_partial = matches!(mode, DisplayMode::Partial);
        let update_sequence = self.firmware.get_update_sequence(is_partial);
        self.execute_sequence(update_sequence)?;
        Ok(())
    }

    fn sleep(&mut self) -> Result<(), DisplayError> {
        let sleep_sequence = self.firmware.get_sleep_sequence();
        self.execute_sequence(sleep_sequence)?;
        Ok(())
    }

    fn get_spec(&self) -> &crate::firmware::DisplaySpec {
        self.firmware.get_spec()
    }

    fn get_write_ram_command(&self) -> u8 {
        self.firmware.get_write_ram_command()
    }
}

// Type alias for the default protocol using current firmware
// Runtime firmware selection
pub enum ConfigurableProtocol {
    EPD128x250(
        GenericEinkProtocol<
            crate::hardware::DefaultGpioController,
            crate::hardware::DefaultSpiController,
            crate::firmware::EPD128x250Firmware,
        >,
    ),
    EPD240x416(
        GenericEinkProtocol<
            crate::hardware::DefaultGpioController,
            crate::hardware::DefaultSpiController,
            crate::firmware::EPD240x416Firmware,
        >,
    ),
}

impl EinkProtocol for ConfigurableProtocol {
    fn init_hardware(&mut self) -> Result<(), DisplayError> {
        match self {
            ConfigurableProtocol::EPD128x250(p) => p.init_hardware(),
            ConfigurableProtocol::EPD240x416(p) => p.init_hardware(),
        }
    }

    fn init_partial(&mut self) -> Result<(), DisplayError> {
        match self {
            ConfigurableProtocol::EPD128x250(p) => p.init_partial(),
            ConfigurableProtocol::EPD240x416(p) => p.init_partial(),
        }
    }

    fn write_cmd(&mut self, cmd: u8) -> Result<(), DisplayError> {
        match self {
            ConfigurableProtocol::EPD128x250(p) => p.write_cmd(cmd),
            ConfigurableProtocol::EPD240x416(p) => p.write_cmd(cmd),
        }
    }

    fn write_data(&mut self, data: u8) -> Result<(), DisplayError> {
        match self {
            ConfigurableProtocol::EPD128x250(p) => p.write_data(data),
            ConfigurableProtocol::EPD240x416(p) => p.write_data(data),
        }
    }

    fn write_image_data(&mut self, data: &[u8]) -> Result<(), DisplayError> {
        match self {
            ConfigurableProtocol::EPD128x250(p) => p.write_image_data(data),
            ConfigurableProtocol::EPD240x416(p) => p.write_image_data(data),
        }
    }

    fn check_status(&mut self) -> Result<(), DisplayError> {
        match self {
            ConfigurableProtocol::EPD128x250(p) => p.check_status(),
            ConfigurableProtocol::EPD240x416(p) => p.check_status(),
        }
    }

    fn update_display(&mut self, mode: DisplayMode) -> Result<(), DisplayError> {
        match self {
            ConfigurableProtocol::EPD128x250(p) => p.update_display(mode),
            ConfigurableProtocol::EPD240x416(p) => p.update_display(mode),
        }
    }

    fn sleep(&mut self) -> Result<(), DisplayError> {
        match self {
            ConfigurableProtocol::EPD128x250(p) => p.sleep(),
            ConfigurableProtocol::EPD240x416(p) => p.sleep(),
        }
    }

    fn get_spec(&self) -> &crate::firmware::DisplaySpec {
        match self {
            ConfigurableProtocol::EPD128x250(p) => p.get_spec(),
            ConfigurableProtocol::EPD240x416(p) => p.get_spec(),
        }
    }

    fn get_write_ram_command(&self) -> u8 {
        match self {
            ConfigurableProtocol::EPD128x250(p) => p.get_write_ram_command(),
            ConfigurableProtocol::EPD240x416(p) => p.get_write_ram_command(),
        }
    }
}

pub type DefaultProtocol = ConfigurableProtocol;

// Helper function to create default protocol
pub fn create_default_protocol() -> Result<DefaultProtocol, DisplayError> {
    let hardware = crate::hardware::DefaultHardwareInterface::new()?;

    // Get the configured firmware type - fail if not configured
    let firmware_type = crate::config::get_default_firmware()?;

    match firmware_type {
        crate::config::FirmwareType::EPD128x250 => {
            let firmware = crate::firmware::EPD128x250Firmware::new();
            let protocol = GenericEinkProtocol::new(hardware, firmware);
            Ok(ConfigurableProtocol::EPD128x250(protocol))
        }
        crate::config::FirmwareType::EPD240x416 => {
            let firmware = crate::firmware::EPD240x416Firmware::new();
            let protocol = GenericEinkProtocol::new(hardware, firmware);
            Ok(ConfigurableProtocol::EPD240x416(protocol))
        }
    }
}

// Helper function to create protocol with custom firmware
pub fn create_protocol_with_firmware<F: DisplayFirmware>(
    firmware: F,
) -> Result<
    GenericEinkProtocol<
        crate::hardware::DefaultGpioController,
        crate::hardware::DefaultSpiController,
        F,
    >,
    DisplayError,
> {
    let hardware = crate::hardware::DefaultHardwareInterface::new()?;
    Ok(GenericEinkProtocol::new(hardware, firmware))
}
