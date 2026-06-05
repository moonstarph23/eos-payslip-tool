#!/bin/bash
# Build script for EOS Payslip Tool Python Sidecar
# This script packages the Python sidecar into a standalone executable

set -e

echo "=========================================="
echo "EOS Payslip Tool - Sidecar Build Script"
echo "=========================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    exit 1
fi

# Check if PyInstaller is installed
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip3 install pyinstaller
fi

cd "$(dirname "$0")/sidecar"

echo "Building sidecar executable..."

# Determine platform and architecture
PLATFORM=$(python3 -c "import platform; print(platform.system().lower())")
ARCH=$(python3 -c "import platform; print(platform.machine())")

if [ "$PLATFORM" = "darwin" ]; then
    if [ "$ARCH" = "arm64" ]; then
        BINARY_NAME="python-sidecar-aarch64-apple-darwin"
        TARGET_TRIPLE="aarch64-apple-darwin"
    else
        BINARY_NAME="python-sidecar-x86_64-apple-darwin"
        TARGET_TRIPLE="x86_64-apple-darwin"
    fi
elif [ "$PLATFORM" = "windows" ] || [ "$PLATFORM" = "cygwin" ] || [ "$PLATFORM" = "msys" ]; then
    BINARY_NAME="python-sidecar-x86_64-pc-windows-msvc"
    TARGET_TRIPLE="x86_64-pc-windows-msvc"
else
    BINARY_NAME="python-sidecar-x86_64-unknown-linux-gnu"
    TARGET_TRIPLE="x86_64-unknown-linux-gnu"
fi

echo "Target platform: $PLATFORM ($ARCH)"
echo "Binary name: $BINARY_NAME"

# Build the sidecar with Tauri naming convention
pyinstaller --onefile --name "$BINARY_NAME" --distpath ../binaries sidecar.py

# Also create a generic symlink/copy for development
if [ "$PLATFORM" = "darwin" ] || [ "$PLATFORM" = "linux" ]; then
    cd ../binaries
    if [ ! -f "python-sidecar" ]; then
        ln -s "$BINARY_NAME" python-sidecar 2>/dev/null || cp "$BINARY_NAME" python-sidecar
    fi
fi

echo ""
echo "Sidecar built successfully!"
echo "Binary location: ../binaries/$BINARY_NAME"
echo ""
echo "Tauri expects the binary at:"
echo "  src-tauri/binaries/$BINARY_NAME"
echo ""
echo "Make sure this path is configured in tauri.conf.json:"
echo '  "externalBin": ["binaries/python-sidecar"]'
echo ""
