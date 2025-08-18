# E-ink Display Firmware Abstraction

This directory contains firmware configurations for different e-ink display variants. The firmware abstraction system allows you to easily support multiple display models with different dimensions and register configurations.

## Architecture

The firmware abstraction consists of:

1. **DisplayFirmware trait** - The interface that all display variants must implement
2. **DisplaySpec** - Holds display specifications (width, height, name, description)
3. **CommandSequence** - A declarative way to define register command sequences
4. **Firmware implementations** - Specific configurations for each display variant

## Adding a New Display Variant

To add support for a new e-ink display variant:

1. **Create a new firmware file** (e.g., `epd240x320.rs`)
2. **Implement the DisplayFirmware trait**
3. **Configure the register sequences** for your specific display
4. **Add the module to mod.rs**

### Example: Creating EPD240x320 Firmware

```rust
// src/firmware/epd240x320.rs
use crate::firmware::{DisplayFirmware, DisplaySpec, CommandSequence};

pub struct EPD240x320Firmware {
    spec: DisplaySpec,
}

impl EPD240x320Firmware {
    pub fn new() -> Self {
        Self {
            spec: DisplaySpec {
                width: 240,
                height: 320,
                name: "EPD240x320".to_string(),
                description: "240x320 E-ink display".to_string(),
            },
        }
    }
}

impl DisplayFirmware for EPD240x320Firmware {
    fn get_spec(&self) -> &DisplaySpec {
        &self.spec
    }

    fn get_init_sequence(&self) -> CommandSequence {
        let height = self.spec.height;
        let width = self.spec.width;
        
        CommandSequence::new()
            // Software reset
            .cmd(0x12)
            .check_status()
            
            // Driver output control - adjusted for 240x320
            .cmd(0x01)
            .data(((height - 1) % 256) as u8)
            .data(((height - 1) / 256) as u8)
            .data(0x00)
            
            // Data entry mode
            .cmd(0x11)
            .data(0x01)
            
            // Set Ram-X address - adjusted for 240x320
            .cmd(0x44)
            .data(0x00)
            .data((width / 8 - 1) as u8)
            
            // Set Ram-Y address - adjusted for 240x320
            .cmd(0x45)
            .data(((height - 1) % 256) as u8)
            .data(((height - 1) / 256) as u8)
            .data(0x00)
            .data(0x00)
            
            // BorderWavefrom - may need different value
            .cmd(0x3C)
            .data(0x03) // Adjusted for this display
            
            // Continue with other initialization commands...
            // (Copy from existing firmware and adjust values)
    }

    fn get_partial_init_sequence(&self) -> CommandSequence {
        CommandSequence::new()
            .cmd(0x3C)
            .data(0x82) // Adjusted for this display
    }

    fn get_update_sequence(&self, is_partial: bool) -> CommandSequence {
        if is_partial {
            CommandSequence::new()
                .cmd(0x22)
                .data(0xCF) // Adjusted for this display
                .cmd(0x20)
                .check_status()
        } else {
            CommandSequence::new()
                .cmd(0x22)
                .data(0xF4) // Adjusted for this display
                .cmd(0x20)
                .check_status()
        }
    }

    fn get_sleep_sequence(&self) -> CommandSequence {
        CommandSequence::new()
            .cmd(0x10)
            .data(0x01)
            .delay(100)
    }

    fn get_write_ram_command(&self) -> u8 {
        0x24 // Usually same across variants
    }
}
```

### Update mod.rs

```rust
// src/firmware/mod.rs
pub mod epd122x250;
pub mod epd200x200;
pub mod epd240x320; // Add your new module

pub use epd122x250::EPD122x250Firmware;
pub use epd200x200::EPD200x200Firmware;
pub use epd240x320::EPD240x320Firmware; // Export your new firmware
```

## Key Register Values to Customize

When creating a new firmware, pay attention to these register values:

### Display Dimensions
- Adjust width/height in DisplaySpec
- Update Ram-X/Ram-Y address calculations in init sequence

### BorderWavefrom (0x3C)
- Full refresh: Often 0x03, 0x05, or 0x07
- Partial refresh: Often 0x80, 0x82, or similar

### Display Update Control (0x22)
- Full refresh: Often 0xF4, 0xF7, or 0xC7
- Partial refresh: Often 0xCF, 0xFF, or similar

### Driver Output Control (0x01)
- Height-dependent values
- Third byte often 0x00 but may vary

## Command Sequence Builder

The CommandSequence provides a fluent API:

```rust
CommandSequence::new()
    .cmd(0x12)           // Write command
    .data(0x01)          // Write data
    .delay(100)          // Wait 100ms
    .check_status()      // Wait for BUSY pin
    .reset()             // Hardware reset
```

## Testing Your Firmware

1. **Build the library**: `make -f Makefile.rust`
2. **Update the default firmware** in `protocol.rs` if needed
3. **Test with your hardware**

## Switching Between Firmware Variants

### At Compile Time
Change the default firmware in `protocol.rs`:

```rust
pub type DefaultProtocol = GenericEinkProtocol<
    crate::hardware::DefaultGpioController,
    crate::hardware::DefaultSpiController,
    crate::firmware::EPD240x320Firmware, // Change this line
>;
```

### At Runtime (Advanced)
Use the generic protocol functions:

```rust
let firmware = EPD240x320Firmware::new();
let protocol = create_protocol_with_firmware(firmware)?;
let display = GenericDisplay::new(protocol);
```

## Common Issues

1. **Wrong dimensions**: Check width/height in DisplaySpec
2. **Display artifacts**: Adjust BorderWavefrom values
3. **Slow/incomplete updates**: Check Display Update Control values
4. **Wrong orientation**: Verify Ram-X/Ram-Y address calculations

## Directory Structure

```
src/firmware/
├── mod.rs              # Main firmware module with trait definition
├── epd122x250.rs       # Current 122x250 display firmware
├── epd200x200.rs       # Example 200x200 display firmware
├── epd240x320.rs       # Your new display firmware
└── README.md           # This documentation
```

This abstraction makes it easy to support new display variants by simply creating a new firmware file with the appropriate register values, without touching the core protocol or hardware logic.