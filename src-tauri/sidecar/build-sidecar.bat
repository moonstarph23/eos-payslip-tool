@echo off
cd /d "%~dp0"

REM Get absolute path to current directory (sidecar folder)
set "SIDEcarDir=%cd%"

REM Build the Python sidecar with all worker files bundled
pyinstaller --clean --onefile --name python-sidecar --distpath "../binaries" --workpath "../target/pyinstaller" --specpath "../target/pyinstaller" ^
  --add-data "%SIDEcarDir%\worker3_standalone.py;." ^
  --add-data "%SIDEcarDir%\worker_standalone.py;." ^
  --add-data "%SIDEcarDir%\worker2_standalone.py;." ^
  --add-data "%SIDEcarDir%\worker4_standalone.py;." ^
  --add-data "%SIDEcarDir%\worker.py;." ^
  sidecar.py

echo.
REM Tauri v1 expects platform-tripled filename
copy "..\binaries\python-sidecar.exe" "..\binaries\python-sidecar-x86_64-pc-windows-msvc.exe" >nul
echo Build complete. Output at: binaries\python-sidecar.exe
echo Also copied to: binaries\python-sidecar-x86_64-pc-windows-msvc.exe
pause
