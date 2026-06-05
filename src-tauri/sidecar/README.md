# EOS Payslip Tool - Python Sidecar

This directory contains the Python sidecar that runs the payroll processing logic.

## Files
- `sidecar.py` - CLI wrapper that communicates with the Tauri Rust backend
- `worker.py` - External PDF payslip processor
- `worker2.py` - Email dispatcher
- `worker3.py` - Internal Excel template processor
- `requirements.txt` - Python dependencies

## Building the Sidecar

### Windows
```bash
cd src-tauri/sidecar
pip install pyinstaller
pyinstaller --onefile --name python-sidecar sidecar.py
```

Copy the resulting `.exe` to `src-tauri/binaries/python-sidecar-x86_64-pc-windows-msvc.exe`

### macOS
```bash
cd src-tauri/sidecar
pip install pyinstaller
pyinstaller --onefile --name python-sidecar sidecar.py
```

Copy the resulting binary to `src-tauri/binaries/python-sidecar-x86_64-apple-darwin`

## Architecture

The sidecar communicates with the Rust backend via:
1. **CLI Arguments** - Commands and file paths passed as args
2. **Stdout JSON** - Results and logs emitted as JSON lines
3. **Exit Code** - 0 for success, 1 for failure

## Commands

- `get_platform` - Returns OS platform info
- `process_external --pdf <path> --employee-data <path> --output-folder <path>` - Process external PDFs
- `process_internal --template <path>` - Process internal Excel template
- `send_emails --manifest <path> --config <json>` - Send payslip emails
