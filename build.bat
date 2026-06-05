@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1

set "SDK_LIB=C:\Program Files (x86)\Windows Kits\10\Lib\10.0.18362.0\um\x64"
set "SDK_INCLUDE=C:\Program Files (x86)\Windows Kits\10\Include\10.0.18362.0\um"
set "SDK_BIN=C:\Program Files (x86)\Windows Kits\10\bin\10.0.18362.0\x64"

set "LIB=%SDK_LIB%;%LIB%"
set "INCLUDE=%SDK_INCLUDE%;%INCLUDE%"
set "PATH=%SDK_BIN%;%PATH%"

set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

cd /d "%~dp0"
npm run tauri dev
