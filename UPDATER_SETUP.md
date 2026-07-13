# Auto-Updater Setup Guide

## Overview

The EOS Payslip Tool includes an auto-updater that checks for new versions and installs them automatically. This guide explains how to set it up.

---

## How It Works

1. **Check** - App downloads workflow-generated `latest.json`, which contains the updater bundle signature
2. **Download** - If an update is found, downloads the signed NSIS updater archive in the background
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
        "https://github.com/YOUR_USERNAME/eos-payslip-tool/releases/latest/download/latest.json"
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

permissions:
  contents: write

jobs:
  release:
    runs-on: windows-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Validate release tag and application versions
        env:
          RELEASE_TAG: ${{ github.ref_name }}
        shell: pwsh
        run: |
          if ($env:RELEASE_TAG -notmatch '^v(\d+\.\d+\.\d+)$') {
            throw "Invalid release tag '$env:RELEASE_TAG'; expected vX.Y.Z"
          }
          $expected = $Matches[1]
          $package = Get-Content -Raw package.json | ConvertFrom-Json
          $packageLock = Get-Content -Raw package-lock.json | ConvertFrom-Json -AsHashTable
          $cargoToml = Get-Content -Raw src-tauri/Cargo.toml
          $cargoLock = Get-Content -Raw src-tauri/Cargo.lock
          $tauriConfig = Get-Content -Raw src-tauri/tauri.conf.json | ConvertFrom-Json
          $settings = Get-Content -Raw src/components/tabs/SettingsTab.tsx
          $sidecar = Get-Content -Raw src-tauri/sidecar/sidecar.py

          $cargoTomlMatch = [regex]::Match($cargoToml, '(?ms)^\[package\]\s*.*?^version\s*=\s*"([^"]+)"')
          $cargoLockMatch = [regex]::Match($cargoLock, '(?ms)^\[\[package\]\]\s*name\s*=\s*"eos-payslip-tool"\s*version\s*=\s*"([^"]+)"')
          $settingsMatch = [regex]::Match($settings, '\bv(\d+\.\d+\.\d+)\b')
          $sidecarMatch = [regex]::Match($sidecar, 'SIDECAR_VERSION\s*=\s*"([^"]+)"')
          if (-not $cargoTomlMatch.Success -or -not $cargoLockMatch.Success -or -not $settingsMatch.Success -or -not $sidecarMatch.Success) {
            throw 'Could not read every application version source'
          }

          $versions = [ordered]@{
            'package.json' = $package.version
            'package-lock.json' = $packageLock['version']
            'package-lock.json root package' = $packageLock['packages']['']['version']
            'src-tauri/Cargo.toml' = $cargoTomlMatch.Groups[1].Value
            'src-tauri/Cargo.lock app package' = $cargoLockMatch.Groups[1].Value
            'src-tauri/tauri.conf.json' = $tauriConfig.package.version
            'src/components/tabs/SettingsTab.tsx' = $settingsMatch.Groups[1].Value
            'src-tauri/sidecar/sidecar.py' = $sidecarMatch.Groups[1].Value
          }
          $mismatches = @($versions.GetEnumerator() | Where-Object Value -ne $expected | ForEach-Object { "$($_.Key)=$($_.Value)" })
          if ($mismatches.Count -gt 0) {
            throw "Release tag $env:RELEASE_TAG expects $expected; mismatches: $($mismatches -join ', ')"
          }
          "Validated release version $expected across tag and application metadata"

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 18
          cache: 'npm'

      - name: Setup Rust
        uses: dtolnay/rust-toolchain@stable

      - name: Install frontend dependencies
        run: npm ci

      - name: Install sidecar dependencies
        run: python -m pip install --disable-pip-version-check -r src-tauri/sidecar/requirements-build.lock

      - name: Test Python sidecar
        run: python -m pytest src-tauri/sidecar/tests -v

      - name: Build Python sidecar
        shell: cmd
        run: src-tauri\build-sidecar.bat

      - name: Smoke test packaged sidecar
        run: python src-tauri/sidecar/tests/packaged_smoke.py --executable src-tauri/binaries/python-sidecar-x86_64-pc-windows-msvc.exe

      - name: Build Tauri app
        uses: tauri-apps/tauri-action@v0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          TAURI_PRIVATE_KEY: ${{ secrets.TAURI_PRIVATE_KEY }}
          TAURI_KEY_PASSWORD: ${{ secrets.TAURI_KEY_PASSWORD }}
        with:
          tagName: ${{ github.ref_name }}
          releaseName: "EOS Payslip Tool ${{ github.ref_name }}"
          updaterJsonPreferNsis: true
          releaseBody: |
            Windows-only release. Download the NSIS `.exe` installer.

            Before publishing this draft, verify that generated `latest.json` has a non-empty `platforms.windows-x86_64.signature` and a ${{ github.ref_name }} NSIS `.nsis.zip` updater URL.
          releaseDraft: true
          prerelease: false
```

This release workflow is intentionally Windows-only. Cross-platform checks remain in `.github/workflows/test.yml`.

---

## Step 5: Create a Release

1. Update the version in:
    - `package.json`
    - `package-lock.json` and its root package entry
    - `src-tauri/Cargo.toml`
    - the `eos-payslip-tool` package in `src-tauri/Cargo.lock`
    - `src-tauri/tauri.conf.json`
    - `src/components/tabs/SettingsTab.tsx`
    - `src-tauri/sidecar/sidecar.py`

2. Commit and tag:
```bash
git add .
git commit -m "Release v1.0.6"
git push origin master
git tag v1.0.6
git push origin v1.0.6
```

3. GitHub Actions will automatically:
    - Validate v1.0.6 against every application version source
    - Build the Windows NSIS `.exe` installer and `.nsis.zip` updater archive
    - Sign the update bundles with your private key
    - Generate `latest.json` containing the updater bundle signature
    - Create a draft GitHub Release with the installer, updater archive/signature, and `latest.json`

4. Inspect the draft Windows installer and generated metadata. Confirm that `platforms.windows-x86_64.signature` is non-empty and its URL points to the tagged release's NSIS `.nsis.zip` updater bundle, then explicitly publish the release.

`latest.json` must never be hand-authored, committed, or manually uploaded. Only publish the metadata generated by `tauri-action`; it embeds the signature of the updater bundle.

---

## Step 6: Test the Updater

1. Install an older version of the app
2. Run it and wait 5 seconds (auto-check on startup)
3. You should see a notification if a newer version exists

---

## Update Endpoint Options

### Option A: GitHub Releases (Recommended)
```json
"endpoints": [
  "https://github.com/YOUR_USERNAME/eos-payslip-tool/releases/latest/download/latest.json"
]
```

The endpoint must resolve to the `latest.json` generated by `tauri-action` in the published release. Its `windows-x86_64` entry must contain a non-empty updater bundle signature and an NSIS updater URL.

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

*For more info, see the [Tauri Updater documentation](https://tauri.app/v1/guides/distribution/updater/)*
