@echo off
setlocal

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    exit /b 1
)

pushd "%~dp0sidecar"
if errorlevel 1 (
    echo ERROR: Could not enter the sidecar directory.
    exit /b 2
)

if exist "..\binaries\python-sidecar*.exe" del /f /q "..\binaries\python-sidecar*.exe"
if exist "..\binaries\python-sidecar*.exe" (
    echo ERROR: Could not remove stale sidecar executable.
    popd
    exit /b 3
)

if exist "..\target\sidecar-venv" rmdir /s /q "..\target\sidecar-venv"
if exist "..\target\sidecar-venv" (
    echo ERROR: Could not remove stale sidecar virtual environment.
    popd
    exit /b 4
)

python -m venv "..\target\sidecar-venv"
if errorlevel 1 (
    echo ERROR: Could not create the sidecar virtual environment.
    popd
    exit /b 5
)

"..\target\sidecar-venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-build.lock
if errorlevel 1 (
    echo ERROR: Could not install locked sidecar dependencies.
    popd
    exit /b 6
)

"..\target\sidecar-venv\Scripts\python.exe" build_sidecar.py
if errorlevel 1 (
    echo ERROR: PyInstaller sidecar build failed.
    popd
    exit /b 7
)

if not exist "..\binaries\python-sidecar-*-pc-windows-msvc.exe" (
    echo ERROR: PyInstaller did not produce a Windows sidecar executable.
    popd
    exit /b 8
)

popd
exit /b 0
