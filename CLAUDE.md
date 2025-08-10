# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Distiller CM5 SDK is a Python SDK for hardware control and AI capabilities on ARM64 Linux devices (Raspberry Pi CM5/Distiller devices). It provides a self-contained environment with hardware drivers for audio, camera, e-ink display, and LED control, plus AI capabilities including ASR (Parakeet/Whisper) and TTS (Piper).

## Common Development Commands

### Package Management
```bash
# Add/remove dependencies (use uv, not pip)
uv add <package>
uv remove <package>
uv sync                    # Update all packages
uv tree                    # Show dependency tree
```

### Building and Testing
```bash
# Download AI models (required before building)
./build.sh                 # Standard models only
./build.sh --whisper       # Include Whisper models

# Build Debian package
./build-deb.sh             # Build package
./build-deb.sh clean       # Clean previous builds
./build-deb.sh whisper     # Build with Whisper models

# Run tests
python -m pytest tests/ -v
```

### Installation (Production)
```bash
sudo dpkg -i dist/distiller-cm5-sdk_*_arm64.deb
sudo apt-get install -f
source /opt/distiller-cm5-sdk/activate.sh
```

## Code Architecture

### Directory Structure
The SDK installs to `/opt/distiller-cm5-sdk/` with this structure:
- `distiller_cm5_sdk/` - Main Python modules
  - `hardware/` - Hardware control (audio, camera, eink, sam/LED)
  - `parakeet/` - Parakeet ASR with VAD
  - `piper/` - Piper TTS
  - `whisper/` - Whisper ASR (optional)
- `models/` - AI model files
- `lib/` - Native libraries (.so files)
- `venv/` - Python 3.11 virtual environment

### Key Architectural Patterns

1. **Model Path Resolution**: The SDK uses a priority system for finding models:
   - Development: Looks in local `models/` directory
   - Production: Uses `/opt/distiller-cm5-sdk/models/`
   - Falls back to downloading if missing

2. **Hardware Abstraction**: Each hardware component has its own module with error handling and resource cleanup:
   - Audio: ALSA-based with configurable gain/volume
   - Camera: V4L2 support with OpenCV integration
   - E-ink: Rust-based SPI driver with multiple firmware support
   - LED: I2C/SPI controllers via SAM module

3. **Configuration Priority**: Environment variables → Config files → Defaults

4. **Native Library Integration**: Rust-based e-ink driver compiled to `.so` and loaded via ctypes

### Important Technical Details

- **Python Version**: Requires Python 3.11+
- **Package Manager**: Uses `uv` (not pip) for dependency management
- **Target Platform**: ARM64 Linux only
- **Build System**: Debian packaging with debhelper
- **CI/CD**: GitHub Actions workflow on ARM64 runners for releases

### Development Notes

- Always use `uv` for package management, never pip directly
- The e-ink display driver is written in Rust and must be compiled before packaging
- Models are downloaded from HuggingFace during build process
- The SDK is designed to be self-contained with its own virtual environment
- Hardware modules include comprehensive error handling and resource cleanup
- Test files are located within module directories (e.g., `hardware/audio/_audio_test.py`)