@echo off
REM Build script for EOS Payslip Tool Python Sidecar
REM This script packages the Python sidecar into a standalone executable

echo ==========================================
echo EOS Payslip Tool - Sidecar Build Script
echo ==========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    exit /b 1
)

REM Check if PyInstaller is installed
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

cd /d "%~dp0\sidecar"

echo Building sidecar executable...

REM Build the sidecar with proper naming for Tauri
REM Tauri expects: {name}-{target-triple}.exe
REM For Windows x64: python-sidecar-x86_64-pc-windows-msvc.exe

pyinstaller --onefile --name python-sidecar-x86_64-pc-windows-msvc --distpath ..\binaries sidecar.py

if errorlevel 1 (
    echo ERROR: Failed to build sidecar
    exit /b 1
)

REM Also create a generic name for development
if exist "..\binaries\python-sidecar-x86_64-pc-windows-msvc.exe" (
    copy "..\binaries\python-sidecar-x86_64-pc-windows-msvc.exe" "..\binaries\python-sidecar.exe" >nul
)

echo.
echo Sidecar built successfully!
echo Binary location: ..\binaries\python-sidecar-x86_64-pc-windows-msvc.exe
echo.
pause
