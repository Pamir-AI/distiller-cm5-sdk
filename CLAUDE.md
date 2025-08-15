# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Distiller CM5 SDK is a Python SDK for hardware control and AI capabilities on ARM64 Linux devices (Raspberry Pi CM5/Distiller devices). It provides a self-contained environment with hardware drivers for audio, camera, e-ink display, and LED control, plus AI capabilities including ASR (Parakeet/Whisper) and TTS (Piper).

## Common Development Commands

### Building and Package Management
```bash
# Download AI models (required before building)
./build.sh                 # Standard models only
./build.sh --whisper       # Include Whisper models

# Build Debian package
./build-deb.sh             # Build package
./build-deb.sh clean       # Clean previous builds
./build-deb.sh whisper     # Build with Whisper models

# Add/remove dependencies (use uv, not pip)
uv add <package>
uv remove <package>
uv sync                    # Update all packages
uv tree                    # Show dependency tree
```

### Testing
```bash
# Run unit tests
python -m pytest tests/ -v

# Run specific test modules
python src/distiller_cm5_sdk/hardware/audio/_audio_test.py
python src/distiller_cm5_sdk/hardware/camera/_camera_unit_test.py
python src/distiller_cm5_sdk/hardware/eink/_display_test.py

# Integration tests
python tests/integration/*.py
```

### Linting and Type Checking
```bash
# Run ruff linter (configured in pyproject.toml)
ruff check src/
ruff format src/

# Type checking (if mypy is available)
mypy src/distiller_cm5_sdk/
```

### Installation (Production)
```bash
sudo dpkg -i dist/distiller-cm5-sdk_*_arm64.deb
sudo apt-get install -f
source /opt/distiller-cm5-sdk/activate.sh
```

## Code Architecture

### Directory Structure
```
distiller-cm5-sdk/
├── src/distiller_cm5_sdk/       # Main SDK source
│   ├── hardware/                # Hardware control modules
│   │   ├── audio/               # Audio capture/playback (ALSA)
│   │   ├── camera/              # Camera control (V4L2/OpenCV)
│   │   ├── eink/                # E-ink display (Rust library + Python)
│   │   │   └── lib/             # Rust source and Makefile
│   │   └── sam/                 # LED control (I2C/SPI)
│   ├── parakeet/                # Parakeet ASR with VAD
│   ├── piper/                   # Piper TTS engine
│   └── whisper/                 # Whisper ASR (optional)
├── debian/                      # Debian packaging files
├── tests/                       # Test suites
│   ├── integration/             # Integration tests
│   └── stress/                  # Stress tests
├── build.sh                     # Model download script
├── build-deb.sh                 # Debian package builder
└── pyproject.toml               # Python package configuration
```

### Key Architectural Patterns

1. **Model Path Resolution**: The SDK uses a priority system for finding models:
   - Development: Looks in local `src/distiller_cm5_sdk/*/models/` directory
   - Production: Uses `/opt/distiller-cm5-sdk/models/`
   - Falls back to downloading if missing

2. **Hardware Abstraction**: Each hardware component has its own module with error handling and resource cleanup:
   - Audio: ALSA-based with configurable gain/volume
   - Camera: V4L2 support with OpenCV integration
   - E-ink: Rust-based SPI driver with multiple firmware support (EPD128x250, EPD240x416)
   - LED: I2C/SPI controllers via SAM module

3. **Configuration Priority**: Environment variables → Config files → Defaults
   - E-ink firmware: `DISTILLER_EINK_FIRMWARE` env var or `/opt/distiller-cm5-sdk/eink.conf`

4. **Native Library Integration**: 
   - Rust-based e-ink driver compiled to `libdistiller_display_sdk_shared.so`
   - Built using `src/distiller_cm5_sdk/hardware/eink/lib/Makefile.rust`
   - Loaded via ctypes in Python

### Important Technical Details

- **Python Version**: Requires Python 3.11+
- **Package Manager**: Uses `uv` (not pip) for dependency management
- **Target Platform**: ARM64 Linux only (aarch64)
- **Build System**: Debian packaging with debhelper
- **CI/CD**: GitHub Actions workflow on ARM64 runners for releases
- **Dependencies**: See `pyproject.toml` for Python deps, `debian/control` for system deps

### Development Notes

- Always use `uv` for package management, never pip directly
- The e-ink display driver is written in Rust and must be compiled before packaging
- Models are downloaded from HuggingFace during build process
- The SDK is designed to be self-contained with its own virtual environment
- Hardware modules include comprehensive error handling and resource cleanup
- Test files are located within module directories (e.g., `hardware/audio/_audio_test.py`)
- The package version is in `pyproject.toml` and `debian/changelog`

### E-ink Display Configuration

The e-ink module supports multiple display types with automatic firmware detection:
- **EPD128x250**: 128×250 pixels (default for backward compatibility)
- **EPD240x416**: 240×416 pixels

Configuration methods (in priority order):
1. Environment variable: `export DISTILLER_EINK_FIRMWARE="EPD240x416"`
2. Config file: `/opt/distiller-cm5-sdk/eink.conf`
3. Programmatic: `set_default_firmware(FirmwareType.EPD240x416)`

### Release Process

1. Update version in `pyproject.toml`
2. Update `debian/changelog` with new version
3. Tag the release: `git tag v0.2.0`
4. Push tags: `git push origin v0.2.0`
5. GitHub Actions will automatically build and create a release