use std::thread;
use std::time::Duration;

use gpiod::{Chip, Input, Lines, Options, Output};
use spidev::{SpiModeFlags, Spidev, SpidevOptions};

use crate::error::DisplayError;

// GPIO pin definitions - these could be made configurable per variant
pub const DC_PIN: u32 = 7; // Data/Command control
pub const RST_PIN: u32 = 13; // Reset
pub const BUSY_PIN: u32 = 9; // Busy status

// GPIO Controller trait for different hardware variants
pub trait GpioController {
    fn new() -> Result<Self, DisplayError>
    where
        Self: Sized;
    fn write_dc(&self, value: bool) -> Result<(), DisplayError>;
    fn write_rst(&self, value: bool) -> Result<(), DisplayError>;
    fn read_busy(&self) -> Result<bool, DisplayError>;
}

// Default GPIO controller implementation
pub struct DefaultGpioController {
    dc_lines: Lines<Output>,
    rst_lines: Lines<Output>,
    busy_lines: Lines<Input>,
}

impl GpioController for DefaultGpioController {
    fn new() -> Result<Self, DisplayError> {
        let chip = Chip::new("/dev/gpiochip0")
            .map_err(|e| DisplayError::Gpio(format!("Failed to open GPIO chip: {}", e)))?;

        // Configure DC pin as output (initially low)
        let dc_opts = Options::output([DC_PIN])
            .values([false])
            .consumer("distiller-display-dc");
        let dc_lines = chip
            .request_lines(dc_opts)
            .map_err(|e| DisplayError::Gpio(format!("Failed to request DC line: {}", e)))?;

        // Configure RST pin as output (initially high)
        let rst_opts = Options::output([RST_PIN])
            .values([true])
            .consumer("distiller-display-rst");
        let rst_lines = chip
            .request_lines(rst_opts)
            .map_err(|e| DisplayError::Gpio(format!("Failed to request RST line: {}", e)))?;

        // Configure BUSY pin as input
        let busy_opts = Options::input([BUSY_PIN]).consumer("distiller-display-busy");
        let busy_lines = chip
            .request_lines(busy_opts)
            .map_err(|e| DisplayError::Gpio(format!("Failed to request BUSY line: {}", e)))?;

        Ok(Self {
            dc_lines,
            rst_lines,
            busy_lines,
        })
    }

    fn write_dc(&self, value: bool) -> Result<(), DisplayError> {
        self.dc_lines
            .set_values([value])
            .map_err(|e| DisplayError::Gpio(format!("Failed to set DC pin: {}", e)))
    }

    fn write_rst(&self, value: bool) -> Result<(), DisplayError> {
        self.rst_lines
            .set_values([value])
            .map_err(|e| DisplayError::Gpio(format!("Failed to set RST pin: {}", e)))
    }

    fn read_busy(&self) -> Result<bool, DisplayError> {
        let values = self
            .busy_lines
            .get_values([false])
            .map_err(|e| DisplayError::Gpio(format!("Failed to read BUSY pin: {}", e)))?;
        Ok(values[0])
    }
}

// SPI Controller trait for different hardware variants
pub trait SpiController {
    fn new() -> Result<Self, DisplayError>
    where
        Self: Sized;
    fn write_all(&mut self, data: &[u8]) -> Result<(), DisplayError>;
}

// Default SPI controller implementation
pub struct DefaultSpiController {
    spi: Spidev,
}

impl SpiController for DefaultSpiController {
    fn new() -> Result<Self, DisplayError> {
        let mut spi = Spidev::open("/dev/spidev0.0")
            .map_err(|e| DisplayError::Spi(format!("Failed to open SPI device: {}", e)))?;

        let options = SpidevOptions::new()
            .bits_per_word(8)
            .max_speed_hz(80_000_000) // Increased from 40MHz to 80MHz for Raspberry Pi CM5
            .mode(SpiModeFlags::SPI_MODE_0)
            .build();

        spi.configure(&options)
            .map_err(|e| DisplayError::Spi(format!("Failed to configure SPI: {}", e)))?;

        Ok(Self { spi })
    }

    fn write_all(&mut self, data: &[u8]) -> Result<(), DisplayError> {
        use std::io::Write;

        // Increased chunk size from 4KB to 32KB for better throughput
        // Modern Linux kernels and Pi CM5 can handle larger transfers
        const MAX_CHUNK_SIZE: usize = 32768; // 32KB chunks

        if data.len() <= MAX_CHUNK_SIZE {
            // Small transfer, send directly
            self.spi
                .write_all(data)
                .map_err(|e| DisplayError::Spi(format!("Failed to write data: {}", e)))
        } else {
            // Large transfer, send in chunks
            for chunk in data.chunks(MAX_CHUNK_SIZE) {
                self.spi
                    .write_all(chunk)
                    .map_err(|e| DisplayError::Spi(format!("Failed to write data chunk: {}", e)))?;

                // Reduced delay from 100μs to 10μs - modern hardware needs less delay
                std::thread::sleep(std::time::Duration::from_micros(10));
            }
            Ok(())
        }
    }
}

// Hardware abstraction layer
pub struct HardwareInterface<G: GpioController, S: SpiController> {
    gpio: G,
    spi: S,
}

impl<G: GpioController, S: SpiController> HardwareInterface<G, S> {
    pub fn new() -> Result<Self, DisplayError> {
        let gpio = G::new()?;
        let spi = S::new()?;
        Ok(Self { gpio, spi })
    }

    pub fn write_dc(&self, value: bool) -> Result<(), DisplayError> {
        self.gpio.write_dc(value)
    }

    pub fn write_rst(&self, value: bool) -> Result<(), DisplayError> {
        self.gpio.write_rst(value)
    }

    pub fn read_busy(&self) -> Result<bool, DisplayError> {
        self.gpio.read_busy()
    }

    pub fn spi_write_all(&mut self, data: &[u8]) -> Result<(), DisplayError> {
        self.spi.write_all(data)
    }
}

// Utility functions
pub fn delay_ms(ms: u64) {
    thread::sleep(Duration::from_millis(ms));
}

pub fn delay_us(us: u64) {
    thread::sleep(Duration::from_micros(us));
}

// Default hardware interface type
pub type DefaultHardwareInterface = HardwareInterface<DefaultGpioController, DefaultSpiController>;
