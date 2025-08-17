use thiserror::Error;

#[derive(Error, Debug)]
pub enum DisplayError {
    #[error("GPIO error: {0}")]
    Gpio(String),
    #[error("SPI error: {0}")]
    Spi(String),
    #[error("PNG error: {0}")]
    Png(String),
    #[error("Display not initialized")]
    NotInitialized,
    #[error("Invalid data size: expected {expected}, got {actual}")]
    InvalidDataSize { expected: usize, actual: usize },
    #[error("Timeout waiting for display")]
    Timeout,
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Configuration error: {0}")]
    Config(String),
}
