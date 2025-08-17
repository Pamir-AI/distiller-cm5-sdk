use crate::error::DisplayError;

pub mod epd128x250;
pub mod epd240x416;

pub use epd128x250::EPD128x250Firmware;
pub use epd240x416::EPD240x416Firmware;

// Display specifications
#[derive(Debug, Clone)]
pub struct DisplaySpec {
    pub width: u32,
    pub height: u32,
    pub name: String,
    pub description: String,
}

impl DisplaySpec {
    pub fn array_size(&self) -> usize {
        ((self.width * self.height) / 8) as usize
    }
}

// Command sequence for display operations
#[derive(Debug, Clone)]
pub struct CommandSequence {
    pub commands: Vec<Command>,
}

#[derive(Debug, Clone)]
pub enum Command {
    WriteCommand(u8),
    WriteData(u8),
    Delay(u64), // milliseconds
    CheckStatus,
    Reset,
}

impl CommandSequence {
    pub fn new() -> Self {
        Self {
            commands: Vec::new(),
        }
    }

    pub fn cmd(mut self, command: u8) -> Self {
        self.commands.push(Command::WriteCommand(command));
        self
    }

    pub fn data(mut self, data: u8) -> Self {
        self.commands.push(Command::WriteData(data));
        self
    }

    pub fn delay(mut self, ms: u64) -> Self {
        self.commands.push(Command::Delay(ms));
        self
    }

    pub fn check_status(mut self) -> Self {
        self.commands.push(Command::CheckStatus);
        self
    }

    pub fn reset(mut self) -> Self {
        self.commands.push(Command::Reset);
        self
    }
}

// Firmware interface trait - implement this for different display variants
pub trait DisplayFirmware {
    fn get_spec(&self) -> &DisplaySpec;
    fn get_init_sequence(&self) -> CommandSequence;
    fn get_partial_init_sequence(&self) -> CommandSequence;
    fn get_update_sequence(&self, is_partial: bool) -> CommandSequence;
    fn get_sleep_sequence(&self) -> CommandSequence;
    fn get_write_ram_command(&self) -> u8;

    // Optional customization points
    fn get_reset_sequence(&self) -> CommandSequence {
        CommandSequence::new().reset().delay(10)
    }

    fn validate_image_size(&self, data: &[u8]) -> Result<(), DisplayError> {
        let expected_size = self.get_spec().array_size();
        if data.len() != expected_size {
            return Err(DisplayError::InvalidDataSize {
                expected: expected_size,
                actual: data.len(),
            });
        }
        Ok(())
    }
}
