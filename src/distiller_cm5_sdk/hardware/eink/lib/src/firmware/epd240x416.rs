use crate::firmware::{CommandSequence, DisplayFirmware, DisplaySpec};

/// Firmware configuration for 240x416 E-ink display
/// Converted from Python EinkDriver with support for multiple initialization modes
pub struct EPD240x416Firmware {
    spec: DisplaySpec,
    /// 4-gray LUT data (216 bytes total)
    lut_4g: [u8; 216],
    /// VCOM LUT for partial updates
    lut_vcom: [u8; 42],
    /// WW LUT for partial updates  
    lut_ww: [u8; 42],
    /// BW LUT for partial updates
    lut_bw: [u8; 42],
    /// WB LUT for partial updates
    lut_wb: [u8; 42],
    /// BB LUT for partial updates
    lut_bb: [u8; 42],
}

impl EPD240x416Firmware {
    pub fn new() -> Self {
        Self {
            spec: DisplaySpec {
                width: 240,
                height: 416,
                name: "EPD240x416".to_string(),
                description: "240x416 E-ink display with 4-gray and partial update support"
                    .to_string(),
            },
            lut_4g: [
                0x01, 0x05, 0x20, 0x19, 0x0A, 0x01, 0x01, 0x05, 0x0A, 0x01, 0x0A, 0x01, 0x01, 0x01,
                0x05, 0x09, 0x02, 0x03, 0x04, 0x01, 0x01, 0x01, 0x04, 0x04, 0x02, 0x00, 0x01, 0x01,
                0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01,
                0x01, 0x05, 0x20, 0x19, 0x0A, 0x01, 0x01, 0x05, 0x4A, 0x01, 0x8A, 0x01, 0x01, 0x01,
                0x05, 0x49, 0x02, 0x83, 0x84, 0x01, 0x01, 0x01, 0x84, 0x84, 0x82, 0x00, 0x01, 0x01,
                0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01,
                0x01, 0x05, 0x20, 0x99, 0x8A, 0x01, 0x01, 0x05, 0x4A, 0x01, 0x8A, 0x01, 0x01, 0x01,
                0x05, 0x49, 0x82, 0x03, 0x04, 0x01, 0x01, 0x01, 0x04, 0x04, 0x02, 0x00, 0x01, 0x01,
                0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01,
                0x01, 0x85, 0x20, 0x99, 0x0A, 0x01, 0x01, 0x05, 0x4A, 0x01, 0x8A, 0x01, 0x01, 0x01,
                0x05, 0x49, 0x02, 0x83, 0x04, 0x01, 0x01, 0x01, 0x04, 0x04, 0x02, 0x00, 0x01, 0x01,
                0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01,
                0x01, 0x85, 0xA0, 0x99, 0x0A, 0x01, 0x01, 0x05, 0x4A, 0x01, 0x8A, 0x01, 0x01, 0x01,
                0x05, 0x49, 0x02, 0x43, 0x04, 0x01, 0x01, 0x01, 0x04, 0x04, 0x42, 0x00, 0x01, 0x01,
                0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01,
                0x09, 0x10, 0x3F, 0x3F, 0x00, 0x0B,
            ],
            lut_vcom: [
                0x01, 0x0a, 0x0a, 0x0a, 0x0a, 0x01, 0x01, 0x02, 0x0f, 0x01, 0x0f, 0x01, 0x01, 0x01,
                0x01, 0x0a, 0x00, 0x0a, 0x00, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            ],
            lut_ww: [
                0x01, 0x4a, 0x4a, 0x0a, 0x0a, 0x01, 0x01, 0x02, 0x8f, 0x01, 0x4f, 0x01, 0x01, 0x01,
                0x01, 0x8a, 0x00, 0x8a, 0x00, 0x01, 0x01, 0x01, 0x80, 0x00, 0x80, 0x00, 0x01, 0x01,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            ],
            lut_bw: [
                0x01, 0x4a, 0x4a, 0x0a, 0x0a, 0x01, 0x01, 0x02, 0x8f, 0x01, 0x4f, 0x01, 0x01, 0x01,
                0x01, 0x8a, 0x00, 0x8a, 0x00, 0x01, 0x01, 0x01, 0x80, 0x00, 0x80, 0x00, 0x01, 0x01,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            ],
            lut_wb: [
                0x01, 0x0a, 0x0a, 0x8a, 0x8a, 0x01, 0x01, 0x02, 0x8f, 0x01, 0x4f, 0x01, 0x01, 0x01,
                0x01, 0x4a, 0x00, 0x4a, 0x00, 0x01, 0x01, 0x01, 0x40, 0x00, 0x40, 0x00, 0x01, 0x01,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            ],
            lut_bb: [
                0x01, 0x0a, 0x0a, 0x8a, 0x8a, 0x01, 0x01, 0x02, 0x8f, 0x01, 0x4f, 0x01, 0x01, 0x01,
                0x01, 0x4a, 0x00, 0x4a, 0x00, 0x01, 0x01, 0x01, 0x40, 0x00, 0x40, 0x00, 0x01, 0x01,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            ],
        }
    }

    /// Get initialization sequence for 4-gray mode (epd_w21_init_4g)
    pub fn get_4g_init_sequence(&self) -> CommandSequence {
        CommandSequence::new()
            // Panel Setting
            .cmd(0x00)
            .data(0xFF) // LUT from MCU
            .data(0x0D)
            // Power Setting
            .cmd(0x01)
            .data(0x03) // Enable internal VSH, VSL, VGH, VGL
            .data(self.lut_4g[211]) // VGH=20V, VGL=-20V
            .data(self.lut_4g[212]) // VSH=15V
            .data(self.lut_4g[213]) // VSL=-15V
            .data(self.lut_4g[214]) // VSHR
            // Booster Soft Start
            .cmd(0x06)
            .data(0xD7)
            .data(0xD7)
            .data(0x27)
            // PLL Control - Frame Rate
            .cmd(0x30)
            .data(self.lut_4g[210]) // PLL
            // CDI Setting
            .cmd(0x50)
            .data(0x57)
            // TCON Setting
            .cmd(0x60)
            .data(0x22)
            // Resolution Setting
            .cmd(0x61)
            .data(0xF0) // HRES[7:3] - 240
            .data(0x01) // VRES[15:8] - 416
            .data(0xA0) // VRES[7:0]
            .cmd(0x65)
            .data(0x00)
            // VCOM_DC Setting
            .cmd(0x82)
            .data(self.lut_4g[215]) // -2.0V
            // Power Saving Register
            .cmd(0xE3)
            .data(0x88) // VCOM_W[3:0], SD_W[3:0]
    }

    /// Write 4-gray LUT sequence
    pub fn get_4g_lut_sequence(&self) -> CommandSequence {
        let mut seq = CommandSequence::new();

        // Write VCOM register (0x20)
        seq = seq.cmd(0x20);
        for i in 0..42 {
            seq = seq.data(self.lut_4g[i]);
        }

        // Write LUTWW register (0x21)
        seq = seq.cmd(0x21);
        for i in 42..84 {
            seq = seq.data(self.lut_4g[i]);
        }

        // Write LUTR register (0x22)
        seq = seq.cmd(0x22);
        for i in 84..126 {
            seq = seq.data(self.lut_4g[i]);
        }

        // Write LUTW register (0x23)
        seq = seq.cmd(0x23);
        for i in 126..168 {
            seq = seq.data(self.lut_4g[i]);
        }

        // Write LUTB register (0x24)
        seq = seq.cmd(0x24);
        for i in 168..210 {
            seq = seq.data(self.lut_4g[i]);
        }

        seq
    }

    /// Get initialization sequence for fast mode (epd_init_fast)
    pub fn get_fast_init_sequence(&self) -> CommandSequence {
        CommandSequence::new()
            .cmd(0x04) // Power on
            .check_status()
            .cmd(0xE0)
            .data(0x02)
            .cmd(0xE5)
            .data(0x5A)
    }

    /// Get initialization sequence for partial update mode (epd_init_part)
    pub fn get_partial_update_init_sequence(&self) -> CommandSequence {
        CommandSequence::new()
            .cmd(0x04) // Power on
            .check_status()
            .cmd(0xE0)
            .data(0x02)
            .cmd(0xE5)
            .data(0x6E)
            .cmd(0x50)
            .data(0xD7)
    }

    /// Get initialization sequence for LUT mode (epd_init_lut)
    pub fn get_lut_init_sequence(&self) -> CommandSequence {
        let mut seq = CommandSequence::new()
            .cmd(0x04) // Power on
            .check_status()
            .cmd(0x00) // Panel setting
            .data(0xF7)
            .cmd(0x09) // Cancel default waveform setting
            // Power setting
            .cmd(0x01)
            .data(0x03)
            .data(0x10)
            .data(0x3F)
            .data(0x3F)
            .data(0x3F)
            // Booster soft start setting
            .cmd(0x06)
            .data(0xD7)
            .data(0xD7)
            .data(0x33)
            // PLL control (frequency setting)
            .cmd(0x30)
            .data(0x09)
            // VCOM and data interval setting
            .cmd(0x50)
            .data(0xD7)
            // Resolution setting
            .cmd(0x61)
            .data(0xF0) // Horizontal resolution
            .data(0x01) // Vertical resolution high 8 bits
            .data(0xA0) // Vertical resolution low 8 bits
            // Gate/Source start position setting
            .cmd(0x2A)
            .data(0x80)
            .data(0x00)
            .data(0x00)
            .data(0xFF)
            .data(0x00)
            // VCOM DC voltage setting
            .cmd(0x82)
            .data(0x0F);

        // Write partial update LUTs
        seq = seq.cmd(0x20); // Write VCOM LUT
        for &val in &self.lut_vcom {
            seq = seq.data(val);
        }

        seq = seq.cmd(0x21); // Write WW LUT
        for &val in &self.lut_ww {
            seq = seq.data(val);
        }

        seq = seq.cmd(0x22); // Write BW LUT
        for &val in &self.lut_bw {
            seq = seq.data(val);
        }

        seq = seq.cmd(0x23); // Write WB LUT
        for &val in &self.lut_wb {
            seq = seq.data(val);
        }

        seq = seq.cmd(0x24); // Write BB LUT
        for &val in &self.lut_bb {
            seq = seq.data(val);
        }

        seq
    }
}

impl DisplayFirmware for EPD240x416Firmware {
    fn get_spec(&self) -> &DisplaySpec {
        &self.spec
    }

    /// Default initialization sequence (basic mode - epd_init)
    fn get_init_sequence(&self) -> CommandSequence {
        CommandSequence::new()
            .cmd(0x04) // Power on
            .check_status()
            .cmd(0x50) // VCOM and data interval setting
            .data(0x97) // Settings for this display
    }

    /// Partial initialization uses fast mode settings
    fn get_partial_init_sequence(&self) -> CommandSequence {
        self.get_fast_init_sequence()
    }

    fn get_update_sequence(&self, is_partial: bool) -> CommandSequence {
        if is_partial {
            // Fast update sequence
            CommandSequence::new()
                .cmd(0x12) // Display refresh
                .delay(1)
                .check_status()
        } else {
            // Full update sequence
            CommandSequence::new()
                .cmd(0x12) // Display refresh
                .delay(1)
                .check_status()
        }
    }

    fn get_sleep_sequence(&self) -> CommandSequence {
        CommandSequence::new()
            .cmd(0x02) // Power off
            .check_status()
            .cmd(0x07) // Deep sleep
            .data(0xA5)
    }

    fn get_write_ram_command(&self) -> u8 {
        0x13 // New data command (primary write command for this display)
    }

    /// Custom reset with longer delays for this display
    fn get_reset_sequence(&self) -> CommandSequence {
        CommandSequence::new()
            .delay(100) // Initial delay
            .reset()
            .delay(20) // Reset delay (longer than default)
    }
}

impl Default for EPD240x416Firmware {
    fn default() -> Self {
        Self::new()
    }
}
