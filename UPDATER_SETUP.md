# Auto-Updater Setup Guide

## Overview

The EOS Payslip Tool includes an auto-updater that checks for new versions and installs them automatically. This guide explains how to set it up.

---

## How It Works

1. **Check** - App queries the GitHub Releases API for new versions
2. **Download** - If update found, downloads the new installer in background
3. **Install** - Installs the update and restarts the app
4. **Notification** - Users see a notification when an update is available

---

## Prerequisites

- A **GitHub repository** for your app
- **GitHub Actions** enabled (for automated builds)
- **Tauri CLI** installed: `cargo install tauri-cli`

---

## Step 1: Generate Signing Keys

Run the key generator script:

```bash
# Windows
cd src-tauri
generate-keys.bat

# macOS/Linux
cd src-tauri
chmod +x generate-keys.sh
./generate-keys.sh
```

Or manually:
```bash
cargo tauri signer generate
```

This creates:
- **Public key** → paste into `tauri.conf.json` → `"pubkey"` field
- **Private key** → save as GitHub Secret `TAURI_PRIVATE_KEY`

---

## Step 2: Update tauri.conf.json

Replace the placeholder in your config:

```json
{
  "tauri": {
    "updater": {
      "active": true,
      "endpoints": [
        "https://api.github.com/repos/YOUR_USERNAME/eos-payslip-tool/releases/latest"
      ],
      "dialog": true,
      "pubkey": "YOUR_PUBLIC_KEY_HERE",
      "windows": {
        "installMode": "quiet"
      }
    }
  }
}
```

**Replace:**
- `YOUR_USERNAME` → your GitHub username or org
- `YOUR_PUBLIC_KEY_HERE` → the public key from Step 1

---

## Step 3: Create GitHub Repository

1. Create a new repo on GitHub: `eos-payslip-tool`
2. Push your code to the repo
3. Go to **Settings → Secrets → Actions**
4. Add a new secret:
   - **Name:** `TAURI_PRIVATE_KEY`
   - **Value:** your private key from Step 1

---

## Step 4: Create GitHub Actions Workflow

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    strategy:
      fail-fast: false
      matrix:
        platform: [macos-latest, ubuntu-latest, windows-latest]
    runs-on: ${{ matrix.platform }}
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: 18
      
      - name: Setup Rust
        uses: dtolnay/rust-action@stable
      
      - name: Install dependencies (Ubuntu only)
        if: matrix.platform == 'ubuntu-latest'
        run: |
          sudo apt-get update
          sudo apt-get install -y libgtk-3-dev libwebkit2gtk-4.0-dev libappindicator3-dev librsvg2-dev patchelf
      
      - name: Install frontend dependencies
        run: npm install
      
      - name: Build Python sidecar
        run: |
          pip install pyinstaller
          cd src-tauri
          # Build sidecar based on platform
          if [ "$RUNNER_OS" == "Windows" ]; then
            build-sidecar.bat
          else
            chmod +x build-sidecar.sh
            ./build-sidecar.sh
          fi
        shell: bash
      
      - name: Build Tauri app
        uses: tauri-apps/tauri-action@v0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          TAURI_PRIVATE_KEY: ${{ secrets.TAURI_PRIVATE_KEY }}
          TAURI_KEY_PASSWORD: ${{ secrets.TAURI_KEY_PASSWORD }}
        with:
          tagName: ${{ github.ref_name }}
          releaseName: "EOS Payslip Tool ${{ github.ref_name }}"
          releaseBody: "See the assets to download this version and install."
          releaseDraft: true
          prerelease: false
```

---

## Step 5: Create a Release

1. Update the version in:
   - `package.json`
   - `src-tauri/Cargo.toml`
   - `src-tauri/tauri.conf.json`

2. Commit and tag:
```bash
git add .
git commit -m "Release v1.0.1"
git tag v1.0.1
git push origin main --tags
```

3. GitHub Actions will automatically:
   - Build the app for Windows, macOS, and Linux
   - Sign the update bundles with your private key
   - Create a GitHub Release with the installers
   - Upload the update metadata (`.sig` files)

---

## Step 6: Test the Updater

1. Install an older version of the app
2. Run it and wait 5 seconds (auto-check on startup)
3. Or go to Settings → Check for Updates
4. You should see a notification if a newer version exists

---

## Update Endpoint Options

### Option A: GitHub Releases (Recommended)
```json
"endpoints": [
  "https://api.github.com/repos/YOUR_USERNAME/eos-payslip-tool/releases/latest"
]
```

### Option B: Static JSON File
Host a JSON file on your own server:
```json
{
  "version": "v1.0.1",
  "notes": "Bug fixes and improvements",
  "pub_date": "2024-01-15T00:00:00Z",
  "signature": "...",
  "url": "https://your-cdn.com/eos-payslip-tool_1.0.1_x64_en-US.msi.zip"
}
```

Then in `tauri.conf.json`:
```json
"endpoints": [
  "https://your-cdn.com/updates/latest.json"
]
```

---

## Security Notes

- **Never commit the private key** to git
- The private key is only needed at build time
- The public key is embedded in the app and safe to share
- Updates are verified using the signature before installation

---

## Troubleshooting

### "No updates available" when there should be
- Check the endpoint URL is correct
- Verify the GitHub release has the `.sig` files attached
- Make sure the version in Cargo.toml matches the tag

### "Signature verification failed"
- Ensure you're using the correct key pair
- The private key at build time must match the public key in the app

### Updates not showing on macOS
- macOS apps must be signed with a valid Apple Developer certificate
- Without signing, Gatekeeper may block updates

---

## Manual Update Check

Users can manually check for updates in the Settings tab:
```typescript
import { checkUpdate } from './hooks/useUpdater';

// This is already built into the app
// The check runs automatically on startup (after 5 seconds)
// And shows a notification if an update is available
```

---

*For more info, see the [Tauri Updater documentation](https://tauri.app/v1/guides/distribution/updater/)*
