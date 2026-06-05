#!/bin/bash
# Generate signing keys for Tauri auto-updater
# Run this script ONCE to create the private/public key pair

set -e

echo "=========================================="
echo "EOS Payslip Tool - Updater Key Generator"
echo "=========================================="
echo ""
echo "This will generate a private/public key pair for signing updates."
echo "KEEP THE PRIVATE KEY SECRET! Add it to your CI/CD environment."
echo ""

# Check if tauri-cli is available
if ! command -v cargo-tauri &> /dev/null; then
    echo "Installing tauri-cli..."
    cargo install tauri-cli
fi

echo "Generating key pair..."
cargo tauri signer generate

echo ""
echo "=========================================="
echo "NEXT STEPS:"
echo "=========================================="
echo "1. Copy the PUBLIC key to src-tauri/tauri.conf.json"
echo "   in the 'pubkey' field under 'updater'"
echo ""
echo "2. Store the PRIVATE key securely in:"
echo "   - GitHub Actions Secret: TAURI_PRIVATE_KEY"
echo "   - Or your CI/CD environment variable"
echo ""
echo "3. Never commit the private key to git!"
echo ""
