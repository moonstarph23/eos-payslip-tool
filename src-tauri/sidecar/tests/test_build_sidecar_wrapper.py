import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
TAURI_DIR = ROOT / "src-tauri"
VENV_DIR = TAURI_DIR / "target" / "sidecar-venv"
BINARY = TAURI_DIR / "binaries" / "python-sidecar-x86_64-pc-windows-msvc.exe"
WRAPPER = TAURI_DIR / "build-sidecar.bat"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows batch regression test")
def test_wrapper_fails_and_removes_stale_binary_when_venv_cannot_be_deleted():
    if Path(sys.executable).resolve().is_relative_to(VENV_DIR.resolve()):
        pytest.skip("Wrapper regression requires a Python outside its disposable venv")

    shutil.rmtree(VENV_DIR, ignore_errors=True)
    VENV_DIR.mkdir(parents=True)
    BINARY.parent.mkdir(parents=True, exist_ok=True)
    BINARY.write_bytes(b"stale executable")

    locker = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        cwd=VENV_DIR,
    )
    time.sleep(0.5)
    try:
        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", str(WRAPPER)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    finally:
        locker.terminate()
        locker.wait(timeout=5)
        shutil.rmtree(VENV_DIR, ignore_errors=True)

    assert completed.returncode == 4
    assert "Could not remove stale sidecar virtual environment" in completed.stdout
    assert not BINARY.exists()
