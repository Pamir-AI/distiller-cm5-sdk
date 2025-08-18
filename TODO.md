# TODO - Project Plans

## Plan 1: Fix Web API Endpoint Issues (eink-web service)

### **Priority: HIGH** - Production service fixes

#### Issues Identified
- [ ] **Missing endpoints (404 errors)**
  - `/api/add-ip-placeholder` - HTML calls this but backend only has `/api/add-placeholder`
  - `/api/add-qr-placeholder` - HTML calls this but backend only has `/api/add-placeholder`
- [ ] **HTTP method mismatch (405 error)**
  - `/api/clear` - Frontend uses GET but backend expects DELETE
- [ ] **Validation error (422)**
  - `/api/add-image` - Frontend sending width/height parameters that backend doesn't accept

#### Implementation Tasks

##### Option A: Add Compatibility Endpoints (Recommended - Less Disruptive)
- [ ] **Add `/api/add-ip-placeholder` endpoint in web_app.py**
  - Create endpoint that calls existing add_placeholder logic with `placeholder_type: "ip"`
- [ ] **Add `/api/add-qr-placeholder` endpoint in web_app.py**  
  - Create endpoint that calls existing add_placeholder logic with `placeholder_type: "qr"`
- [ ] **Add GET method support for `/api/clear` endpoint**
  - Add GET handler that calls same logic as DELETE method
- [ ] **Fix add-image endpoint validation**
  - Remove width/height parameter validation or handle them properly

##### Option B: Fix Frontend (Alternative)
- [ ] **Update templates/index.html**
  - Change `/api/add-ip-placeholder` to `/api/add-placeholder` with `placeholder_type: "ip"`
  - Change `/api/add-qr-placeholder` to `/api/add-placeholder` with `placeholder_type: "qr"`
  - Change clear function to use DELETE method instead of GET
  - Remove width/height parameters from add-image request

#### Testing
- [ ] Test all API endpoints after fixes
- [ ] Verify frontend functionality works correctly
- [ ] Check error handling for edge cases

---

## Plan 2: E-ink Display Refactor (128x250 → 122x250)

### **Priority: MEDIUM** - Major architectural change

#### Critical Mathematical Issue
**Non-Byte-Aligned Width Problem:**
- Current (128 pixels): 128 ÷ 8 = 16 bytes/row (perfectly aligned)
- New (122 pixels): 122 ÷ 8 = 15.25 bytes/row → requires 16 bytes/row with 6 bits padding
- Total array size remains: 4000 bytes (16 bytes/row × 250 rows)

#### Phase 1: Core Rust Firmware Files (CRITICAL)

- [ ] **Fix array_size() calculation in mod.rs**
  - File: `src/distiller_cm5_sdk/hardware/eink/lib/src/firmware/mod.rs`
  - Line 20: Change `((self.width * self.height) / 8)` to `(((self.width + 7) / 8) * self.height)`

- [ ] **Rename and update epd128x250.rs → epd122x250.rs**
  - File: `src/distiller_cm5_sdk/hardware/eink/lib/src/firmware/epd128x250.rs`
  - [ ] Line 6: `EPD128x250Firmware` → `EPD122x250Firmware`
  - [ ] Line 14: `width: 128` → `width: 122`
  - [ ] Line 16: `"EPD128x250"` → `"EPD122x250"`
  - [ ] Line 17: Update description text
  - [ ] Line 47: RAM address calculation: `(width / 8 - 1)` → `((width + 7) / 8 - 1)`

#### Phase 2: Image Processing (CRITICAL)

- [ ] **Update bit packing logic in image.rs**
  - File: `src/distiller_cm5_sdk/hardware/eink/lib/src/image.rs`
  - Lines 33-38: Implement row-aware bit packing
  ```rust
  let bytes_per_row = (image.width + 7) / 8;
  let byte_idx = y * bytes_per_row + (x / 8);
  let bit_idx = 7 - (x % 8);
  ```

- [ ] **Fix image_processing.rs for row padding**
  - File: `src/distiller_cm5_sdk/hardware/eink/lib/src/image_processing.rs`
  - [ ] Line 99: Update `pack_1bit_data` to handle row padding
  - [ ] Lines 540-605: Fix both ARM64 and fallback implementations
  - [ ] Implement proper bytes_per_row calculation

#### Phase 3: Configuration System Updates

- [ ] **Update config.rs**
  - File: `src/distiller_cm5_sdk/hardware/eink/lib/src/config.rs`
  - Lines to update: 2, 8, 16, 29-32, 41, 93-94, 179-184, 222, 230-231
  - Replace all `EPD128x250` with `EPD122x250`

- [ ] **Update protocol.rs**
  - File: `src/distiller_cm5_sdk/hardware/eink/lib/src/protocol.rs`
  - Lines to update: 142-146, 161, 168, 175, 182, 189, 196, 203, 210, 217, 224, 240-243
  - Update all EPD128x250 references

#### Phase 4: Python Display Module

- [ ] **Update display.py**
  - File: `src/distiller_cm5_sdk/hardware/eink/display.py`
  - [ ] Line 37: `EPD128x250 = "EPD128x250"` → `EPD122x250 = "EPD122x250"`
  - [ ] Lines 605, 640, 665: Update error messages
  - [ ] Line 793: `src_width, src_height = 250, 128` → `250, 122`
  - [ ] Line 806: Update comments
  - [ ] Line 1448: Fix array size calculation if hardcoded
  - [ ] Lines 1519, 1646, 1683: Update documentation

#### Phase 5: Test Files

- [ ] **Update _display_test.py**
  - File: `src/distiller_cm5_sdk/hardware/eink/_display_test.py`
  - Lines 176-177, 202, 206: Update firmware references and dimensions

- [ ] **Update test_display.rs**
  - File: `src/distiller_cm5_sdk/hardware/eink/lib/src/bin/test_display.rs`
  - Lines 389, 418: Update test values

#### Phase 6: Composer UI Module (23 locations)

- [ ] **Update all composer/ directory files**
  - [ ] Replace all `128x250` → `122x250`
  - [ ] Replace all width references from `128` to `122`
  - [ ] Update canvas dimensions in web interface
  - [ ] Update UI layout calculations

#### Phase 7: Documentation

- [ ] **Update README.md**
  - Replace all `EPD128x250` → `EPD122x250`
  - Replace all `128x250` → `122x250`

- [ ] **Update CLAUDE.md**
  - Update dimension descriptions and examples

- [ ] **Update eink.conf.example**
  - Update configuration examples

#### Testing & Validation

- [ ] **Byte Alignment Testing**
  - [ ] Verify 16 bytes per row with proper padding
  - [ ] Test padding bits are consistently set to 0

- [ ] **Image Conversion Testing**
  - [ ] Test all image formats handle 122-pixel width
  - [ ] Verify no corruption at row boundaries

- [ ] **Bit Packing Validation**
  - [ ] Ensure padding bits don't affect display
  - [ ] Test edge cases with pixels near row boundaries

- [ ] **Display Controller Testing**
  - [ ] Confirm hardware accepts new configuration
  - [ ] Test RAM X address end calculation: `((122 + 7) / 8 - 1) = 15`

- [ ] **Transformation Testing**
  - [ ] Test rotation operations with non-aligned width
  - [ ] Test flip operations handle padding correctly

#### Migration Strategy

- [ ] **Phase A: Preparation**
  - [ ] Create new firmware file `epd122x250.rs` alongside existing
  - [ ] Update configuration to support both variants temporarily
  - [ ] Implement feature flags for testing

- [ ] **Phase B: Core Implementation**
  - [ ] Implement byte-aligned array_size calculation
  - [ ] Fix all bit packing operations to be row-aware
  - [ ] Update critical path components first

- [ ] **Phase C: Testing & Rollout**
  - [ ] Comprehensive testing with real hardware
  - [ ] Update all string references and documentation
  - [ ] Remove old epd128x250 support after validation

#### Risk Mitigation

- [ ] **High Risk: Display Controller Compatibility**
  - [ ] Test with actual hardware early in process
  - [ ] Have rollback plan ready

- [ ] **Medium Risk: Existing Image Compatibility**
  - [ ] Create image migration tool for 128x250 → 122x250
  - [ ] Document breaking changes for users

- [ ] **Low Risk: Performance Impact**
  - [ ] Monitor padding overhead (6 bits × 250 rows = 1875 bits wasted)
  - [ ] Optimize if necessary

---

## Key Implementation Notes

### Critical Formula Changes
Throughout the codebase, replace:
```rust
// OLD: byte_index = pixel_index / 8
// NEW: byte_index = (y * bytes_per_row) + (x / 8)
//      where bytes_per_row = (width + 7) / 8
```

### Padding Management
- Last 6 bits of each row are padding (pixels 122-127)
- Must be consistently set (typically to 0 for white)
- Image processing must not write to padding bits

### Display Controller RAM
- RAM X address end: `((122 + 7) / 8 - 1) = 15`
- Total RAM usage: `16 bytes × 250 rows = 4000 bytes`

---

## Timeline Estimates

### Plan 1 (Web API Fixes): 1-2 days
- Quick fixes for production service
- Low complexity, high impact

### Plan 2 (E-ink Refactor): 2-3 weeks
- Complex architectural change
- Requires careful testing and validation
- High impact on entire system

## Dependencies
- Plan 1 can proceed independently
- Plan 2 requires hardware testing setup
- Both plans should coordinate if they affect shared components

