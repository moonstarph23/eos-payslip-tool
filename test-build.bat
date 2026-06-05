@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1

set "SDK_LIB=C:\Program Files (x86)\Windows Kits\10\Lib\10.0.18362.0\um\x64"
set "LIB=%SDK_LIB%;%LIB%"

set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

cd /d "C:\Users\Romel Aquino\Desktop\Projects\Raizel\Payslip - Modern\payslip-tauri\src-tauri"

echo LIB=%LIB%
echo.
cargo build 2>&1
