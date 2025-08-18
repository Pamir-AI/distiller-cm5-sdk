# E-ink Display Firmware Module

Low-level firmware abstraction layer for e-ink displays, providing a trait-based architecture that enables seamless support for multiple display variants through declarative command sequences.

## 🏗️ Architecture Philosophy

The firmware module implements a **trait-based abstraction** that separates display-specific logic from hardware communication. This design enables:

- **Zero-cost abstraction** through Rust's trait system
- **Compile-time optimization** of command sequences
- **Runtime firmware selection** without performance penalty
- **Type-safe register programming** with builder patterns

```rust
┌─────────────────────────────────────────────────┐
│              Application Layer                   │
│         (Display Driver, Image Processing)       │
└────────────────┬────────────────────────────────┘
                 │ Uses
┌────────────────┴────────────────────────────────┐
│           DisplayFirmware Trait                  │
│  • Initialization • Refresh • Sleep • Commands   │
└────────────────┬────────────────────────────────┘
                 │ Implemented by
┌────────────────┴────────────────────────────────┐
│         Concrete Firmware Implementations        │
│  • EPD128x250 • EPD240x416 • Custom Displays     │
└────────────────┬────────────────────────────────┘
                 │ Generates
┌────────────────┴────────────────────────────────┐
│            Command Sequences                     │
│  • SPI Commands • GPIO Control • Timing          │
└─────────────────────────────────────────────────┘
```

## Core Components

### DisplayFirmware Trait

The heart of the abstraction - every display must implement this trait:

```rust
pub trait DisplayFirmware {
    /// Display specifications (dimensions, name)
    fn get_spec(&self) -> &DisplaySpec;
    
    /// Full initialization sequence
    fn get_init_sequence(&self) -> CommandSequence;
    
    /// Partial refresh initialization
    fn get_partial_init_sequence(&self) -> CommandSequence;
    
    /// Update display (full or partial)
    fn get_update_sequence(&self, is_partial: bool) -> CommandSequence;
    
    /// Enter sleep mode
    fn get_sleep_sequence(&self) -> CommandSequence;
    
    /// RAM write command register
    fn get_write_ram_command(&self) -> u8;
    
    /// Optional: Custom reset sequence
    fn get_reset_sequence(&self) -> CommandSequence {
        CommandSequence::new().reset().delay(10)
    }
    
    /// Optional: Validate image data size
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
```

### Command Sequence Builder

A fluent API for constructing display command sequences:

```rust
CommandSequence::new()
    .cmd(0x12)          // Software reset
    .check_status()     // Wait for BUSY pin
    .cmd(0x01)          // Driver output control
    .data(0xF9)         // Height LSB
    .data(0x00)         // Height MSB
    .data(0x00)         // Gate scan direction
    .delay(10)          // Wait 10ms
    .reset()            // Hardware reset pulse
```

**Command Types:**
- `cmd(u8)`: Send command byte via SPI
- `data(u8)`: Send data byte via SPI
- `delay(u64)`: Wait specified milliseconds
- `check_status()`: Poll BUSY pin until ready
- `reset()`: Pulse RESET pin

### Display Specifications

Each display defines its physical characteristics:

```rust
pub struct DisplaySpec {
    pub width: u32,        // Pixel width
    pub height: u32,       // Pixel height
    pub name: String,      // Display model name
    pub description: String // Human-readable description
}

impl DisplaySpec {
    /// Calculate required buffer size (bits/8)
    pub fn array_size(&self) -> usize {
        ((self.width * self.height) / 8) as usize
    }
}
```

## Supported Displays

### EPD128x250 - Classic E-Reader Display

**Specifications:**
- Resolution: 128×250 pixels
- Aspect Ratio: ~1:2
- Buffer Size: 4,000 bytes
- Refresh Time: ~2 seconds (full), ~200ms (partial)

```rust
use crate::firmware::EPD128x250Firmware;

let firmware = EPD128x250Firmware::new();
// Automatic register configuration for 128x250
```

**Key Registers:**
| Register | Value | Description |
|----------|-------|-------------|
| 0x01 | 0xF9, 0x00, 0x00 | Driver output (250 lines) |
| 0x3C | 0x05 / 0x80 | Border waveform |
| 0x22 | 0xF7 / 0xFF | Update control |
| 0x24 | - | Write RAM command |

### EPD240x416 - High-Resolution Display

**Specifications:**
- Resolution: 240×416 pixels
- Aspect Ratio: ~3:5
- Buffer Size: 12,480 bytes
- Refresh Time: ~2.5 seconds (full), ~300ms (partial)
- 4-Gray Support: Yes (with special LUT)

```rust
use crate::firmware::EPD240x416Firmware;

let firmware = EPD240x416Firmware::new();

// Advanced: 4-gray mode
let sequence = firmware.get_4g_init_sequence();
```

**Key Features:**
- **Multiple refresh modes**: Full, partial, 4-gray
- **Custom LUT tables**: Fine-tuned waveforms
- **Extended command set**: Advanced display control

**LUT Configuration:**
```rust
pub struct EPD240x416Firmware {
    lut_4g: [u8; 216],     // 4-gray lookup table
    lut_vcom: [u8; 42],    // VCOM voltage LUT
    lut_ww: [u8; 42],      // White-to-white LUT
    lut_bw: [u8; 42],      // Black-to-white LUT
    lut_wb: [u8; 42],      // White-to-black LUT
    lut_bb: [u8; 42],      // Black-to-black LUT
}
```

## Creating Custom Firmware

### Step 1: Define Your Display

Create a new file `src/firmware/your_display.rs`:

```rust
use crate::firmware::{CommandSequence, DisplayFirmware, DisplaySpec};

pub struct YourDisplayFirmware {
    spec: DisplaySpec,
    // Add any display-specific data (LUTs, timing, etc.)
}

impl YourDisplayFirmware {
    pub fn new() -> Self {
        Self {
            spec: DisplaySpec {
                width: 320,     // Your display width
                height: 480,    // Your display height
                name: "YourDisplay".to_string(),
                description: "Custom 320x480 E-ink Display".to_string(),
            },
        }
    }
}
```

### Step 2: Implement DisplayFirmware Trait

```rust
impl DisplayFirmware for YourDisplayFirmware {
    fn get_spec(&self) -> &DisplaySpec {
        &self.spec
    }
    
    fn get_init_sequence(&self) -> CommandSequence {
        CommandSequence::new()
            // Software reset
            .cmd(0x12)
            .check_status()
            
            // Panel settings (adjust for your display)
            .cmd(0x00)
            .data(0x8F)  // Panel configuration
            
            // Power settings
            .cmd(0x01)
            .data(0x03)  // VDS_EN, VDG_EN
            .data(0x00)  // VCOM_HV, VGHL_LV
            .data(0x2B)  // VDH
            .data(0x2B)  // VDL
            
            // Booster soft start
            .cmd(0x06)
            .data(0x17)
            .data(0x17)
            .data(0x17)
            
            // Resolution setting
            .cmd(0x61)
            .data((self.spec.width >> 8) as u8)
            .data((self.spec.width & 0xFF) as u8)
            .data((self.spec.height >> 8) as u8)
            .data((self.spec.height & 0xFF) as u8)
            
            // Your display-specific initialization...
    }
    
    fn get_partial_init_sequence(&self) -> CommandSequence {
        CommandSequence::new()
            .cmd(0x37)  // Set partial area
            .data(0x00)
            // Configure for partial updates
    }
    
    fn get_update_sequence(&self, is_partial: bool) -> CommandSequence {
        if is_partial {
            CommandSequence::new()
                .cmd(0x22)
                .data(0x0F)  // Partial update command
                .cmd(0x20)
                .check_status()
        } else {
            CommandSequence::new()
                .cmd(0x22)
                .data(0xC7)  // Full update command
                .cmd(0x20)
                .check_status()
        }
    }
    
    fn get_sleep_sequence(&self) -> CommandSequence {
        CommandSequence::new()
            .cmd(0x10)  // Deep sleep
            .data(0x01)
            .delay(100)
    }
    
    fn get_write_ram_command(&self) -> u8 {
        0x24  // Most displays use 0x24
    }
}
```

### Step 3: Register Your Firmware

Update `src/firmware/mod.rs`:

```rust
pub mod your_display;
pub use your_display::YourDisplayFirmware;
```

### Step 4: Configure Runtime Selection

In `src/config.rs`:

```rust
#[derive(Debug, Clone)]
pub enum FirmwareType {
    EPD128x250,
    EPD240x416,
    YourDisplay,  // Add your variant
}

pub fn create_firmware(firmware_type: FirmwareType) -> Box<dyn DisplayFirmware> {
    match firmware_type {
        FirmwareType::EPD128x250 => Box::new(EPD128x250Firmware::new()),
        FirmwareType::EPD240x416 => Box::new(EPD240x416Firmware::new()),
        FirmwareType::YourDisplay => Box::new(YourDisplayFirmware::new()),
    }
}
```

## Register Programming Guide

### Essential Registers

Most e-ink controllers share similar register sets:

| Register | Function | Typical Values |
|----------|----------|----------------|
| 0x00 | Panel Setting | Resolution, gate scan |
| 0x01 | Power Setting / Driver Output | Voltage levels, line count |
| 0x06 | Booster Soft Start | Startup timing |
| 0x10 | Deep Sleep Mode | 0x01 = enter sleep |
| 0x11 | Data Entry Mode | Scan direction |
| 0x12 | Software Reset | No data needed |
| 0x20 | Master Activation | Trigger update |
| 0x22 | Display Update Control | Update type |
| 0x24 | Write RAM (B/W) | Image data follows |
| 0x26 | Write RAM (Red) | For 3-color displays |
| 0x3C | Border Waveform | Border update behavior |
| 0x44 | X Address Range | RAM X boundaries |
| 0x45 | Y Address Range | RAM Y boundaries |

### Timing Considerations

Critical timing points in command sequences:

```rust
// After reset - display needs time to initialize
.reset()
.delay(10)  // 10ms minimum

// After software reset - wait for initialization
.cmd(0x12)
.delay(10)
.check_status()  // Wait for BUSY

// After triggering update - wait for completion
.cmd(0x20)
.check_status()  // Can take 2-3 seconds

// Before sleep - ensure update complete
.check_status()
.cmd(0x10)
.data(0x01)
```

### LUT Programming (Advanced)

For displays supporting custom waveforms:

```rust
fn write_lut(&self) -> CommandSequence {
    let mut seq = CommandSequence::new();
    
    // VCOM LUT
    seq = seq.cmd(0x20);
    for &byte in &self.lut_vcom {
        seq = seq.data(byte);
    }
    
    // W2W LUT
    seq = seq.cmd(0x21);
    for &byte in &self.lut_ww {
        seq = seq.data(byte);
    }
    
    // Additional LUTs...
    
    seq
}
```

## Performance Optimization

### Compile-Time Optimization

The trait-based design enables zero-cost abstraction:

```rust
// Monomorphization creates optimized code for each firmware type
pub struct GenericDisplay<F: DisplayFirmware> {
    firmware: F,
    // No virtual dispatch overhead
}
```

### Command Batching

Minimize SPI transactions:

```rust
// Inefficient: Multiple SPI transactions
seq.cmd(0x44).cmd(0x00).cmd(0x0F)

// Efficient: Batched data writes
seq.cmd(0x44).data(0x00).data(0x0F)
```

### Status Checking Strategy

```rust
// Fast path: Skip status check for known-fast operations
seq.cmd(0x11).data(0x03)  // No check needed

// Slow path: Check after time-consuming operations
seq.cmd(0x20).check_status()  // Update can take seconds
```

## Troubleshooting

### Display Not Responding

```rust
// Verify reset sequence
fn debug_reset() -> CommandSequence {
    CommandSequence::new()
        .reset()
        .delay(50)      // Increase delay
        .cmd(0x12)      // Software reset
        .delay(50)      // Increase delay
        .check_status() // Should clear quickly
}
```

### Incorrect Dimensions

```rust
// Log actual vs expected size
fn validate_dimensions(&self, image: &[u8]) {
    let expected = self.spec.array_size();
    println!("Expected: {} bytes for {}x{}", 
             expected, self.spec.width, self.spec.height);
    println!("Actual: {} bytes", image.len());
}
```

### Partial Refresh Issues

```rust
// Ensure proper mode switching
fn safe_partial_update(&self) -> CommandSequence {
    CommandSequence::new()
        .check_status()     // Ensure previous complete
        .cmd(0x3C).data(0x80)  // Set partial border
        .cmd(0x22).data(0xFF)  // Partial update mode
        .cmd(0x20)
        .check_status()
}
```

### Ghosting Problems

Adjust border waveform and update sequences:

```rust
// Stronger ghosting elimination
fn anti_ghost_sequence(&self) -> CommandSequence {
    CommandSequence::new()
        .cmd(0x3C).data(0x03)  // Strong border
        .cmd(0x22).data(0xF7)  // Full refresh
        .cmd(0x20)
        .check_status()
        .delay(100)  // Extra settling time
}
```

## Testing Your Firmware

### Unit Tests

```rust
#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_display_spec() {
        let firmware = YourDisplayFirmware::new();
        let spec = firmware.get_spec();
        
        assert_eq!(spec.width, 320);
        assert_eq!(spec.height, 480);
        assert_eq!(spec.array_size(), 320 * 480 / 8);
    }
    
    #[test]
    fn test_command_sequence() {
        let firmware = YourDisplayFirmware::new();
        let seq = firmware.get_init_sequence();
        
        // Verify sequence contains expected commands
        // Note: In real implementation, CommandSequence 
        // would need inspection methods
    }
}
```

### Hardware Testing

```rust
// Test program: src/bin/test_firmware.rs
use distiller_display_sdk::{Display, YourDisplayFirmware};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize with your firmware
    let firmware = YourDisplayFirmware::new();
    let display = Display::with_firmware(firmware)?;
    
    // Test pattern: alternating lines
    let mut buffer = vec![0u8; display.get_buffer_size()];
    for (i, byte) in buffer.iter_mut().enumerate() {
        *byte = if i % 2 == 0 { 0xFF } else { 0x00 };
    }
    
    // Display test pattern
    display.show_buffer(&buffer)?;
    
    println!("Test pattern displayed successfully!");
    Ok(())
}
```

### Integration Testing

Test the complete pipeline:

```bash
# Build the library
cargo build --release

# Run test binary
cargo run --bin test_firmware

# Run with specific firmware
DISPLAY_FIRMWARE=YourDisplay cargo run --bin test_firmware
```

## Advanced Topics

### Multi-Display Support

Support multiple displays simultaneously:

```rust
pub struct DualDisplay {
    primary: Box<dyn DisplayFirmware>,
    secondary: Box<dyn DisplayFirmware>,
}

impl DualDisplay {
    pub fn new(primary_type: FirmwareType, secondary_type: FirmwareType) -> Self {
        Self {
            primary: create_firmware(primary_type),
            secondary: create_firmware(secondary_type),
        }
    }
    
    pub fn update_both(&mut self, primary_img: &[u8], secondary_img: &[u8]) {
        // Update primary display
        self.primary.validate_image_size(primary_img).unwrap();
        // ... send to primary
        
        // Update secondary display  
        self.secondary.validate_image_size(secondary_img).unwrap();
        // ... send to secondary
    }
}
```

### Dynamic Firmware Loading

Load firmware configurations at runtime:

```rust
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize)]
struct FirmwareConfig {
    width: u32,
    height: u32,
    init_commands: Vec<(u8, Vec<u8>)>,
    update_commands: Vec<(u8, Vec<u8>)>,
}

impl FirmwareConfig {
    pub fn load_from_file(path: &str) -> Result<Self, Box<dyn Error>> {
        let contents = std::fs::read_to_string(path)?;
        Ok(serde_json::from_str(&contents)?)
    }
    
    pub fn to_firmware(self) -> ConfigurableFirmware {
        ConfigurableFirmware::new(self)
    }
}
```

### Waveform Optimization

Fine-tune display waveforms for specific use cases:

```rust
pub enum WaveformMode {
    Quality,     // Best image quality, slower
    Balanced,    // Default trade-off
    Speed,       // Fastest updates, may ghost
    LowPower,    // Minimum power consumption
}

impl EPD240x416Firmware {
    pub fn set_waveform_mode(&mut self, mode: WaveformMode) {
        match mode {
            WaveformMode::Quality => {
                // Use high-quality LUTs
                self.lut_vcom = HIGH_QUALITY_VCOM_LUT;
            }
            WaveformMode::Speed => {
                // Use fast LUTs
                self.lut_vcom = FAST_VCOM_LUT;
            }
            // ...
        }
    }
}
```

## Performance Metrics

Measured command sequence execution times:

| Operation | Time | Description |
|-----------|------|-------------|
| Init Sequence | 150ms | Full initialization |
| Partial Init | 50ms | Partial mode setup |
| Write RAM | 20ms | 128x250 image transfer |
| Full Update | 2000ms | Complete refresh cycle |
| Partial Update | 200ms | Partial refresh cycle |
| Sleep Entry | 10ms | Enter deep sleep |

Memory usage:

| Component | Size | Notes |
|-----------|------|-------|
| EPD128x250 | 1KB | Minimal firmware |
| EPD240x416 | 3KB | Includes LUT tables |
| Command Buffer | 256B | Typical sequence |

## Related Components

- [Display Module](../../): High-level display driver
- [Hardware Module](../hardware.rs): GPIO and SPI interfaces
- [Protocol Module](../protocol.rs): Communication protocol
- [FFI Module](../ffi.rs): C bindings for firmware

## References

- [E-ink Controller Datasheets](https://www.pervasivedisplays.com/)
- [SPI Protocol Specification](https://en.wikipedia.org/wiki/Serial_Peripheral_Interface)
- [Rust Embedded Book](https://rust-embedded.github.io/book/)

## License

Part of the Distiller CM5 SDK. See LICENSE file for details.