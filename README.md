# EOS Payslip Tool

A modern, cross-platform desktop application for payroll processing built with **Tauri** + **React** + **Tailwind CSS**, designed using **Google Stitch**.

---

## Architecture

```
payslip-tauri/
├── src/                          # React 18 + TypeScript Frontend
│   ├── components/
│   │   ├── Sidebar.tsx           # Dark sidebar with nav
│   │   ├── TopBar.tsx            # Window chrome + status
│   │   ├── LogConsole.tsx        # Bottom terminal panel
│   │   ├── UpdateNotification.tsx # Auto-update notifications
│   │   └── tabs/
│   │       ├── ExternalTab.tsx   # PDF processing (real file dialogs!)
│   │       ├── InternalTab.tsx   # Excel template (real file dialogs!)
│   │       ├── EmailTab.tsx      # Email sending (real file dialogs!)
│   │       └── SettingsTab.tsx   # About, updates, support
│   ├── hooks/
│   │   ├── useTauri.ts           # Tauri API wrappers
│   │   └── useUpdater.ts         # Auto-update logic
│   ├── App.tsx                   # Main shell + tab routing
│   └── index.css                 # Tailwind + custom styles
├── src-tauri/                    # Rust Backend
│   ├── src/
│   │   └── main.rs               # Rust commands + sidecar + updater
│   ├── sidecar/                  # Python Sidecar
│   │   ├── sidecar.py            # CLI wrapper (JSON I/O)
│   │   ├── worker.py             # External PDF processor (copied)
│   │   ├── worker2.py            # Email dispatcher (copied)
│   │   ├── worker3.py            # Internal Excel processor (copied)
│   │   └── requirements.txt      # Python deps
│   ├── binaries/                 # Built sidecar executables
│   ├── .github/
│   │   └── workflows/
│   │       ├── release.yml       # GitHub Actions release
│   │       └── test.yml          # CI test build
│   ├── Cargo.toml                # Rust dependencies
│   ├── tauri.conf.json           # Window config, permissions, updater
│   ├── build-sidecar.bat         # Windows sidecar build
│   ├── build-sidecar.sh          # macOS/Linux sidecar build
│   ├── generate-keys.bat         # Windows updater key gen
│   └── generate-keys.sh        # macOS/Linux updater key gen
├── tailwind.config.js            # EOS design system tokens
└── UPDATER_SETUP.md              # Detailed updater setup guide
```

---

## Features

### Payroll Processing
- **External Tab** - Split bulk PDF payslips, encrypt with birthday passwords
- **Internal Tab** - Generate payslips from Excel template with VBA macro
- **Email Tab** - Send payslips via Gmail SMTP with customizable templates

### Modern UI (from Stitch)
- Dark sidebar navigation with Deep Purple accent
- Clean card-based layout with 16px radius
- Real-time log console with color-coded entries
- Progress bars with shimmer animations
- Native OS file dialogs (no custom file pickers!)

### Auto-Updater
- Checks for updates on startup (after 5 seconds)
- Shows notification when update is available
- One-click install and restart
- Signed updates for security
- GitHub Releases integration

### Cross-Platform
- **Windows** - Full functionality + NSIS `.exe` installer
- **macOS** - External + Email tabs + .dmg installer
- **Linux** - Basic support + .AppImage

---

## Quick Start

### Prerequisites
- [Node.js](https://nodejs.org/) v18+
- [Rust](https://rustup.rs/)
- [Python](https://python.org/) 3.12

### 1. Install Node Dependencies
```bash
cd payslip-tauri
npm install
```

### 2. Build the Python Sidecar
```bash
cd src-tauri

# Windows
build-sidecar.bat

# macOS/Linux
chmod +x build-sidecar.sh
./build-sidecar.sh
```

### 3. Run in Development
```bash
npm run tauri dev
```

### 4. Build Installer
```bash
npm run tauri build
```

**Output:**
- **Windows:** NSIS `.exe` installer
- **Windows updater:** Signed NSIS `.nsis.zip` archive and `.sig` file

---

## Auto-Updater Setup

The app includes an auto-updater that checks GitHub Releases for new versions.

### Quick Setup
1. Create a GitHub repository for your app
2. Run the key generator: `cd src-tauri && ./generate-keys.sh` (or `.bat`)
3. Copy the **public key** to `tauri.conf.json` → `"pubkey"` field
4. Add the **private key** as GitHub Secret: `TAURI_PRIVATE_KEY`
5. Update the endpoint in `tauri.conf.json`:
   ```json
   "endpoints": [
     "https://github.com/YOUR_USERNAME/eos-payslip-tool/releases/latest/download/latest.json"
   ]
   ```
6. Push `master` and tag v1.0.6: `git push origin master && git tag v1.0.6 && git push origin v1.0.6`
7. GitHub Actions builds a Windows-only draft release and generates `latest.json` containing the updater bundle signature
8. Before publishing, verify a non-empty `platforms.windows-x86_64.signature` and the tagged release's NSIS `.nsis.zip` URL in `latest.json`
9. Inspect the Windows NSIS `.exe` installer and explicitly publish the draft

`latest.json` is workflow-generated metadata that embeds the updater bundle signature. Never hand-author, commit, or manually upload it.

**Detailed instructions:** See [UPDATER_SETUP.md](UPDATER_SETUP.md)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18 + TypeScript |
| Styling | Tailwind CSS + Custom animations |
| Desktop | Tauri v1 (Rust) |
| Backend Logic | Python 3.12 (PyPDF2, pandas, openpyxl) |
| Icons | Material Symbols |
| Fonts | Geist, JetBrains Mono |
| Build | Vite |
| CI/CD | GitHub Actions |

---

## Tauri Commands

| Command | Description |
|---------|-------------|
| `select_file` | Open native file dialog |
| `select_files` | Open native multi-file dialog |
| `select_folder` | Open native folder dialog |
| `open_folder` | Open folder in system explorer |
| `get_platform` | Get current OS (windows/macos/linux) |
| `spawn_sidecar` | Run Python sidecar with command |
| `check_update` | Check for app updates |
| `install_update` | Download and install update |

---

## Design System (from Stitch)

- **Primary Accent:** Deep Purple `#5E1A5E` (EOS brand)
- **Fonts:** Geist (UI), JetBrains Mono (logs)
- **Layout:** Sidebar (280px) + Content + Log Console
- **Cards:** White, 16px radius, soft shadow
- **Animations:** Shimmer progress, smooth transitions

---

## GitHub Actions

The repository includes two workflows:

### Release Workflow (`.github/workflows/release.yml`)
- Triggered on version tags (`v*`)
- Builds the Windows NSIS `.exe` installer and signed `.nsis.zip` updater archive/signature
- Packages Python sidecar automatically
- Signs updates with private key
- Creates a draft GitHub Release for inspection and explicit publication

### Test Workflow (`.github/workflows/test.yml`)
- Runs cross-platform on pushes to `master`, `main`, or `develop`
- Builds the app in debug mode
- Validates TypeScript compilation

---

## Development Tips

### Enable DevTools
DevTools are auto-enabled in debug builds. Press `Ctrl + Shift + I` (or `Cmd + Option + I` on Mac).

### Hot Reload
Frontend code auto-reloads on save. Rust code rebuilds automatically in `tauri dev`.

### Adding New Workers
1. Copy worker Python file to `src-tauri/sidecar/`
2. Add command handler in `sidecar.py`
3. Update React component to call the command

---

## Troubleshooting

### Sidecar not found
Ensure the binary exists at `src-tauri/binaries/` with proper naming:
- Windows: `python-sidecar-x86_64-pc-windows-msvc.exe`
- macOS Intel: `python-sidecar-x86_64-apple-darwin`
- macOS ARM: `python-sidecar-aarch64-apple-darwin`

### Updates not working
- Check `UPDATER_SETUP.md` for full instructions
- Ensure the GitHub repo is public (or use a static JSON endpoint)
- Verify the public/private key pair matches

### macOS Internal Tab
Excel COM automation is Windows-only. To use on Mac:
- Port the VBA macro to pure Python using `openpyxl`
- Or hide the Internal tab on macOS

---

## Credits

- **UI Design:** Google Stitch (EOS Payslip Tool project)
- **Framework:** Tauri by the Tauri Studio
- **Frontend:** React by Meta
- **Styling:** Tailwind CSS

---

*Built for EOS Global Expansion*
