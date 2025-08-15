#!/bin/bash

# Distiller CM5 SDK Installation Script
# This script replicates the Debian package installation process
# Usage: ./install.sh [OPTIONS]
#   OPTIONS:
#     --uninstall    Remove the SDK
#     --whisper      Include Whisper models during installation
#     --help         Show this help message

set -e

# Configuration
INSTALL_DIR="/opt/distiller-cm5-sdk"
SDK_VERSION="0.1.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to create directory if it doesn't exist
make_dir_if_not_exists() {
    if [ ! -d "$1" ]; then
        print_info "Creating directory: $1"
        sudo mkdir -p "$1"
    fi
}

# Function to download a file if it doesn't exist
download_if_not_exists() {
    local url="$1"
    local output_path="$2"
    if [ ! -f "$output_path" ]; then
        print_info "Downloading $output_path"
        curl -L "$url" -o "$output_path"
    else
        print_info "File already exists: $output_path"
    fi
}

# Show help message
show_help() {
    cat << EOF
Distiller CM5 SDK Installation Script

Usage: $0 [OPTIONS]

OPTIONS:
    --uninstall    Remove the SDK from the system
    --whisper      Include Whisper models during installation
    --help         Show this help message

EXAMPLES:
    Install SDK without Whisper models:
        $0

    Install SDK with Whisper models:
        $0 --whisper

    Uninstall SDK:
        $0 --uninstall

The SDK will be installed to: $INSTALL_DIR
EOF
}

# Uninstall function
uninstall_sdk() {
    print_info "Starting Distiller CM5 SDK uninstallation..."
    
    # Check if SDK is installed
    if [ ! -d "$INSTALL_DIR" ]; then
        print_warning "SDK is not installed at $INSTALL_DIR"
        exit 0
    fi
    
    # Check for processes using SDK files
    print_info "Checking for processes using SDK files..."
    
    if command_exists lsof; then
        # Check virtual environment
        VENV_PROCESSES=$(lsof +D "$INSTALL_DIR/.venv" 2>/dev/null | grep -v COMMAND || true)
        if [ -n "$VENV_PROCESSES" ]; then
            print_warning "Some processes are still using the SDK virtual environment:"
            echo "$VENV_PROCESSES"
            read -p "Continue with uninstallation? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_info "Uninstallation cancelled"
                exit 1
            fi
        fi
        
        # Check shared library
        if [ -f "$INSTALL_DIR/lib/libdistiller_eink.so" ]; then
            LIB_PROCESSES=$(lsof "$INSTALL_DIR/lib/libdistiller_eink.so" 2>/dev/null | grep -v COMMAND || true)
            if [ -n "$LIB_PROCESSES" ]; then
                print_warning "Some processes are still using the SDK shared library:"
                echo "$LIB_PROCESSES"
                read -p "Continue with uninstallation? (y/N): " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    print_info "Uninstallation cancelled"
                    exit 1
                fi
            fi
        fi
    fi
    
    print_info "Removing SDK files..."
    
    # Remove virtual environment
    if [ -d "$INSTALL_DIR/.venv" ]; then
        print_info "Removing virtual environment..."
        sudo rm -rf "$INSTALL_DIR/.venv"
    fi
    
    # Remove uv-related files
    sudo rm -f "$INSTALL_DIR/uv.lock"
    sudo rm -f "$INSTALL_DIR/.python-version"
    
    # Remove convenience scripts
    sudo rm -f "$INSTALL_DIR/activate.sh"
    sudo rm -f "$INSTALL_DIR/README"
    
    # Remove symlink to shared library
    sudo rm -f /usr/lib/libdistiller_eink.so
    
    # Update shared library cache
    sudo ldconfig
    
    # Remove the entire installation directory
    print_info "Removing $INSTALL_DIR directory..."
    sudo rm -rf "$INSTALL_DIR"
    
    print_success "Distiller CM5 SDK uninstalled successfully"
}

# Installation function
install_sdk() {
    local include_whisper=$1
    
    print_info "Starting Distiller CM5 SDK installation..."
    
    # Check if we're in the right directory
    if [ ! -f "$SCRIPT_DIR/pyproject.toml" ] || [ ! -d "$SCRIPT_DIR/src" ]; then
        print_error "This script must be run from the distiller-cm5-sdk root directory"
        exit 1
    fi
    
    # Check system architecture
    ARCH=$(uname -m)
    if [ "$ARCH" != "aarch64" ] && [ "$ARCH" != "arm64" ]; then
        print_warning "This SDK is designed for ARM64 architecture. Current architecture: $ARCH"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Installation cancelled"
            exit 1
        fi
    fi
    
    # Install system dependencies
    print_info "Installing system dependencies..."
    DEPS="python3 python3-dev python3-venv curl ca-certificates alsa-utils libasound2 libasound2-plugins portaudio19-dev libasound2-dev build-essential pkg-config"
    
    if command_exists apt-get; then
        print_info "Installing required packages: $DEPS"
        sudo apt-get update
        sudo apt-get install -y $DEPS || print_warning "Some packages may have failed to install"
    else
        print_warning "apt-get not found. Please ensure the following packages are installed:"
        echo "$DEPS"
    fi
    
    # Check for Rust (needed to build e-ink library)
    if ! command_exists cargo; then
        print_warning "Rust/Cargo not found. Installing Rust..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source "$HOME/.cargo/env"
    fi
    
    # Build Rust library
    print_info "Building Rust e-ink display library..."
    cd "$SCRIPT_DIR/src/distiller_cm5_sdk/hardware/eink/lib"
    
    # Install ARM64 target if needed
    if command_exists rustup; then
        rustup target add aarch64-unknown-linux-gnu 2>/dev/null || true
    fi
    
    # Build the library
    make -f Makefile.rust clean
    make -f Makefile.rust build
    
    if [ ! -f "libdistiller_eink.so" ]; then
        print_error "Failed to build Rust library"
        exit 1
    fi
    
    print_info "Rust library built successfully"
    cd "$SCRIPT_DIR"
    
    # Download models
    print_info "Downloading AI models..."
    
    # Parakeet models
    PARAKEET_DIR="$SCRIPT_DIR/src/distiller_cm5_sdk/parakeet/models"
    make_dir_if_not_exists "$PARAKEET_DIR"
    
    download_if_not_exists "https://huggingface.co/tommy1900/Parakeet-onnx/resolve/main/encoder.onnx" "$PARAKEET_DIR/encoder.onnx"
    download_if_not_exists "https://huggingface.co/tommy1900/Parakeet-onnx/resolve/main/decoder.onnx" "$PARAKEET_DIR/decoder.onnx"
    download_if_not_exists "https://huggingface.co/tommy1900/Parakeet-onnx/resolve/main/joiner.onnx" "$PARAKEET_DIR/joiner.onnx"
    download_if_not_exists "https://huggingface.co/tommy1900/Parakeet-onnx/resolve/main/tokens.txt" "$PARAKEET_DIR/tokens.txt"
    download_if_not_exists "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx" "$PARAKEET_DIR/silero_vad.onnx"
    
    # Piper models and executable
    PIPER_MODEL_DIR="$SCRIPT_DIR/src/distiller_cm5_sdk/piper/models"
    PIPER_EXE_DIR="$SCRIPT_DIR/src/distiller_cm5_sdk/piper/piper"
    make_dir_if_not_exists "$PIPER_MODEL_DIR"
    make_dir_if_not_exists "$PIPER_EXE_DIR"
    
    # Download Piper executable if needed
    PIPER_TAR="$SCRIPT_DIR/src/distiller_cm5_sdk/piper/piper_arm64.tar.gz"
    if [ ! -f "$PIPER_EXE_DIR/piper" ]; then
        print_info "Downloading Piper executable..."
        download_if_not_exists "https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_arm64.tar.gz" "$PIPER_TAR"
        tar -xf "$PIPER_TAR" -C "$SCRIPT_DIR/src/distiller_cm5_sdk/piper"
        rm -f "$PIPER_TAR"
    fi
    
    # Download Piper voice model
    download_if_not_exists "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx?download=true" "$PIPER_MODEL_DIR/en_US-amy-medium.onnx"
    download_if_not_exists "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx.json?download=true" "$PIPER_MODEL_DIR/en_US-amy-medium.onnx.json"
    
    # Whisper models (optional)
    if [ "$include_whisper" = true ]; then
        print_info "Downloading Whisper models..."
        WHISPER_DIR="$SCRIPT_DIR/src/distiller_cm5_sdk/whisper/models/faster-distil-whisper-small.en"
        make_dir_if_not_exists "$WHISPER_DIR"
        
        download_if_not_exists "https://huggingface.co/Systran/faster-distil-whisper-small.en/resolve/main/model.bin?download=true" "$WHISPER_DIR/model.bin"
        download_if_not_exists "https://huggingface.co/Systran/faster-distil-whisper-small.en/resolve/main/config.json?download=true" "$WHISPER_DIR/config.json"
        download_if_not_exists "https://huggingface.co/Systran/faster-distil-whisper-small.en/resolve/main/preprocessor_config.json?download=true" "$WHISPER_DIR/preprocessor_config.json"
        download_if_not_exists "https://huggingface.co/Systran/faster-distil-whisper-small.en/resolve/main/tokenizer.json?download=true" "$WHISPER_DIR/tokenizer.json"
        download_if_not_exists "https://huggingface.co/Systran/faster-distil-whisper-small.en/resolve/main/vocabulary.json?download=true" "$WHISPER_DIR/vocabulary.json"
    fi
    
    # Create installation directory
    print_info "Creating installation directory at $INSTALL_DIR..."
    sudo mkdir -p "$INSTALL_DIR"
    sudo mkdir -p "$INSTALL_DIR/lib"
    sudo mkdir -p "$INSTALL_DIR/models"
    sudo mkdir -p "$INSTALL_DIR/bin"
    
    # Copy SDK files
    print_info "Copying SDK files to $INSTALL_DIR..."
    
    # Copy Python source code
    sudo cp -r "$SCRIPT_DIR/src" "$INSTALL_DIR/"
    
    # Copy models
    sudo cp -r "$SCRIPT_DIR/src/distiller_cm5_sdk/parakeet/models" "$INSTALL_DIR/models/parakeet"
    sudo cp -r "$SCRIPT_DIR/src/distiller_cm5_sdk/piper/models" "$INSTALL_DIR/models/piper"
    sudo cp -r "$SCRIPT_DIR/src/distiller_cm5_sdk/piper/piper" "$INSTALL_DIR/models/piper/"
    
    if [ "$include_whisper" = true ] && [ -d "$SCRIPT_DIR/src/distiller_cm5_sdk/whisper/models" ]; then
        sudo cp -r "$SCRIPT_DIR/src/distiller_cm5_sdk/whisper/models" "$INSTALL_DIR/models/whisper"
    fi
    
    # Copy Rust library
    sudo cp "$SCRIPT_DIR/src/distiller_cm5_sdk/hardware/eink/lib/libdistiller_eink.so" "$INSTALL_DIR/lib/"
    
    # Create symlink for shared library
    sudo ln -sf "$INSTALL_DIR/lib/libdistiller_eink.so" /usr/lib/libdistiller_eink.so
    
    # Copy configuration files
    sudo cp "$SCRIPT_DIR/pyproject.toml" "$INSTALL_DIR/"
    
    # Install uv if not available
    print_info "Setting up uv package manager..."
    UV_BINARY=""
    
    if command_exists uv; then
        UV_BINARY="uv"
    elif [ -f "/usr/local/bin/uv" ] && [ -x "/usr/local/bin/uv" ]; then
        UV_BINARY="/usr/local/bin/uv"
    else
        print_info "Installing uv package manager..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        
        # Make uv available system-wide
        if [ -f "$HOME/.local/bin/uv" ]; then
            sudo cp "$HOME/.local/bin/uv" /usr/local/bin/uv 2>/dev/null || true
            sudo cp "$HOME/.local/bin/uvx" /usr/local/bin/uvx 2>/dev/null || true
            sudo chmod +x /usr/local/bin/uv /usr/local/bin/uvx 2>/dev/null || true
            UV_BINARY="/usr/local/bin/uv"
        fi
    fi
    
    # Verify uv installation
    if [ -z "$UV_BINARY" ] || ! command_exists "$UV_BINARY"; then
        print_error "Failed to install uv package manager"
        exit 1
    fi
    
    print_info "Using uv at: $UV_BINARY"
    
    # Create virtual environment using uv
    cd "$INSTALL_DIR"
    print_info "Creating Python virtual environment using uv..."
    
    # Clean up any existing virtual environment
    sudo rm -rf .venv 2>/dev/null || true
    sudo rm -f uv.lock 2>/dev/null || true
    
    # Create fresh virtual environment
    sudo "$UV_BINARY" venv .venv
    
    # Install dependencies using uv sync
    print_info "Installing Python dependencies using uv sync..."
    print_info "Generating architecture-specific lockfile and installing dependencies..."
    
    if ! sudo "$UV_BINARY" sync; then
        print_error "Failed to install Python dependencies with uv sync"
        print_info "This could be due to missing system dependencies or network issues"
        print_info "Please check that required system packages are installed:"
        print_info "  - portaudio19-dev (for pyaudio)"
        print_info "  - build-essential (for native extensions)"
        print_info "  - pkg-config (for library detection)"
        exit 1
    fi
    
    # Verify virtual environment
    VENV_PYTHON="$INSTALL_DIR/.venv/bin/python"
    if [ ! -f "$VENV_PYTHON" ]; then
        print_error "Virtual environment setup failed"
        exit 1
    fi
    
    # Test basic imports
    print_info "Verifying Python package installation..."
    if ! sudo "$VENV_PYTHON" -c "import sys; print('Python version:', sys.version)"; then
        print_error "Python environment verification failed"
        exit 1
    fi
    
    # Test SDK imports
    print_info "Testing distiller-cm5-sdk imports..."
    if ! sudo "$VENV_PYTHON" -c "import distiller_cm5_sdk; print('SDK imported successfully')"; then
        print_error "distiller-cm5-sdk import failed"
        exit 1
    fi
    
    print_info "Installation verification completed successfully"
    
    # Create activation script
    cat > /tmp/activate.sh << 'EOF'
#!/bin/bash
# Activate the distiller-cm5-sdk virtual environment
source /opt/distiller-cm5-sdk/.venv/bin/activate
export PYTHONPATH="/opt/distiller-cm5-sdk/src:$PYTHONPATH"
export LD_LIBRARY_PATH="/opt/distiller-cm5-sdk/lib:$LD_LIBRARY_PATH"
echo "Distiller CM5 SDK environment activated"
echo "Python packages available: distiller_cm5_sdk"
echo "Models available in: /opt/distiller-cm5-sdk/models/"
echo "Shared library: /opt/distiller-cm5-sdk/lib/libdistiller_eink.so"
echo ""
echo "Package management with uv:"
echo "  Add package: cd /opt/distiller-cm5-sdk && uv add <package>"
echo "  Remove package: cd /opt/distiller-cm5-sdk && uv remove <package>"
echo "  Update dependencies: cd /opt/distiller-cm5-sdk && uv sync"
echo ""
echo "Installation was successful!"
EOF
    
    sudo mv /tmp/activate.sh "$INSTALL_DIR/activate.sh"
    sudo chmod +x "$INSTALL_DIR/activate.sh"
    
    # Create README file
    cat > /tmp/README << 'EOF'
Distiller CM5 SDK - Manual Installation
========================================

This SDK was installed using the install.sh script.

The SDK uses uv for Python package management.

Usage:
1. Activate the environment: source /opt/distiller-cm5-sdk/activate.sh
2. Use the SDK in your projects by setting PYTHONPATH and LD_LIBRARY_PATH

For dependent projects (like distiller-cm5-mcp-hub and distiller-cm5-services):
- Set PYTHONPATH to include /opt/distiller-cm5-sdk/src
- Set LD_LIBRARY_PATH to include /opt/distiller-cm5-sdk/lib
- Use the virtual environment at /opt/distiller-cm5-sdk/.venv

Package management:
- To add packages: cd /opt/distiller-cm5-sdk && uv add <package>
- To remove packages: cd /opt/distiller-cm5-sdk && uv remove <package>
- To sync packages: cd /opt/distiller-cm5-sdk && uv sync

To uninstall the SDK:
Run the install.sh script with --uninstall flag
EOF
    
    sudo mv /tmp/README "$INSTALL_DIR/README"
    
    # Set proper permissions
    sudo chown -R root:root "$INSTALL_DIR"
    sudo chmod -R 755 "$INSTALL_DIR"
    sudo chmod 644 "$INSTALL_DIR/README"
    
    # Update shared library cache
    sudo ldconfig
    
    print_success "Distiller CM5 SDK installed successfully to $INSTALL_DIR"
    print_info "Python virtual environment created with uv package manager"
    print_info "All Python dependencies installed via uv sync"
    print_info "To activate the environment, run: source $INSTALL_DIR/activate.sh"
}

# Main script logic
main() {
    local mode="install"
    local include_whisper=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --uninstall)
                mode="uninstall"
                shift
                ;;
            --whisper)
                include_whisper=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Check if running as root (warn but don't require)
    if [ "$EUID" -eq 0 ]; then
        print_warning "Running as root. The script will use sudo when needed."
    fi
    
    # Execute based on mode
    case $mode in
        install)
            install_sdk $include_whisper
            ;;
        uninstall)
            uninstall_sdk
            ;;
        *)
            print_error "Invalid mode: $mode"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"