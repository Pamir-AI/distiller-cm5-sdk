#!/bin/bash

# Script Name: build-deb.sh
# Description: Build the distiller-cm5-sdk Debian package
# Usage: ./build-deb.sh [clean] [whisper]

set -e

# Configuration
PACKAGE_NAME="distiller-cm5-sdk"
DIST_DIR="dist"
TARGET_ARCHITECTURES="arm64"

# Function to check if command exists
command_exists() {
	command -v "$1" >/dev/null 2>&1
}

# Parse arguments
CLEAN_BUILD=false
INCLUDE_WHISPER=false

for arg in "$@"; do
	case $arg in
	clean)
		CLEAN_BUILD=true
		shift
		;;
	whisper)
		INCLUDE_WHISPER=true
		shift
		;;
	*)
		echo "Unknown option: $arg"
		echo "Usage: $0 [clean] [whisper]"
		exit 1
		;;
	esac
done

echo "[INFO] Building distiller-cm5-sdk Debian package..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -d "debian" ]; then
	echo "[ERROR] This script must be run from the distiller-cm5-sdk root directory"
	exit 1
fi

# Check for required tools
check_command() {
	if ! command -v "$1" &>/dev/null; then
		echo "[ERROR] Required command '$1' not found. Please install it first."
		exit 1
	fi
}

echo "[INFO] Checking build dependencies..."
check_command "dpkg-buildpackage"

# Clean previous builds if requested
if [ "$CLEAN_BUILD" = true ]; then
	echo "[INFO] Cleaning previous builds..."
	sudo rm -rf build/ dist/ *.egg-info/ .venv/
	sudo rm -f ../distiller-cm5-sdk_*.deb ../distiller-cm5-sdk_*.dsc ../distiller-cm5-sdk_*.tar.gz ../distiller-cm5-sdk_*.changes ../distiller-cm5-sdk_*.buildinfo
	sudo rm -f distiller-cm5-sdk_*.deb distiller-cm5-sdk_*.dsc distiller-cm5-sdk_*.tar.gz distiller-cm5-sdk_*.changes
	sudo rm -f distiller_cm5_sdk-*.whl distiller_cm5_sdk-*.tar.gz
	sudo debian/rules clean || true
	# Clean Rust library
	cd src/distiller_cm5_sdk/hardware/eink/lib && make -f Makefile.rust clean && cd ../../../../..
	echo "[INFO] Clean complete."
	exit 0
fi

# Build the Rust library
echo "[INFO] Building Rust library..."
cd src/distiller_cm5_sdk/hardware/eink/lib

# Show build info
make -f Makefile.rust target-info

# Install target if needed
make -f Makefile.rust install-target

# Build the library
make -f Makefile.rust clean
make -f Makefile.rust build

# Verify library was created
if [ ! -f "libdistiller_display_sdk_shared.so" ]; then
	echo "[ERROR] Rust library was not created"
	exit 1
fi

# Show library architecture info
echo "[INFO] Library architecture:"
file libdistiller_display_sdk_shared.so

echo "[INFO] Rust library built successfully"
cd ../../../../..

# Download models
if [ "$INCLUDE_WHISPER" = true ]; then
	echo "[INFO] Downloading models including Whisper..."
	./build.sh whisper
else
	echo "[INFO] Downloading models (excluding Whisper)..."
	./build.sh
fi

# Note: uv.lock is not generated during package build to avoid architecture conflicts
# The postinst script will generate the lock file during installation on the target system
echo "[INFO] Skipping uv.lock generation (will be generated during installation)"

# Build Debian package
print_status() {
	echo -e "[INFO] $1"
}

print_success() {
	echo -e "[SUCCESS] $1"
}

print_warning() {
	echo -e "[WARNING] $1"
}

print_error() {
	echo -e "[ERROR] $1"
}

print_status "Building Debian package for $PACKAGE_NAME"

export DEB_BUILD_OPTIONS="parallel=$(nproc)"

# Build for ARM64 architecture
for arch in $TARGET_ARCHITECTURES; do
	print_status "Building for architecture: $arch ..."

	# Try with dpkg-buildpackage first
	dpkg-buildpackage -us -uc -b -d -a$arch
done

# Organize build artifacts
mkdir -p "$DIST_DIR"
for arch in $TARGET_ARCHITECTURES; do
	for file in ../${PACKAGE_NAME}_*_${arch}.deb; do
		if [ -f "$file" ]; then
			mv -f "$file" "$DIST_DIR/"
			DEB_BASENAME=$(basename "$file")
			print_status "Package moved: $DIST_DIR/$DEB_BASENAME"
			# Show package info
			print_status "Package contents ($DEB_BASENAME):"
			dpkg -c "$DIST_DIR/$DEB_BASENAME" | head -20
			echo "..."
			print_status "Package information ($DEB_BASENAME):"
			dpkg -I "$DIST_DIR/$DEB_BASENAME"
		fi
	done
done

# Clean up any other .deb files in parent directory
for file in ../${PACKAGE_NAME}_*.deb; do
	if [[ "$file" != *"_all.deb" && "$file" != *"_arm64.deb" ]]; then
		rm -f "$file"
	fi
done

print_success "Build process completed successfully!"

# Show final status
if [ -d "$DIST_DIR" ] && [ "$(ls -A "$DIST_DIR" 2>/dev/null)" ]; then
	echo
	print_status "Generated packages:"
	ls -la "$DIST_DIR/"
	echo
	print_status "To install the package, run:"
	echo "  sudo dpkg -i $DIST_DIR/${PACKAGE_NAME}_*_arm64.deb"
	echo "  sudo apt-get install -f  # Fix any dependency issues"
fi
