"""Build the Python sidecar with all runtime-only dependencies bundled."""

from pathlib import Path
import platform

import PyInstaller.__main__


SIDECAR_DIR = Path(__file__).resolve().parent
TAURI_DIR = SIDECAR_DIR.parent


def target_triple():
    system = platform.system()
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        architecture = "aarch64"
    elif machine in {"amd64", "x86_64"}:
        architecture = "x86_64"
    else:
        raise RuntimeError(f"Unsupported sidecar build architecture: {machine}")

    if system == "Windows":
        return f"{architecture}-pc-windows-msvc"
    if system == "Darwin":
        return f"{architecture}-apple-darwin"
    if system == "Linux":
        return f"{architecture}-unknown-linux-gnu"
    raise RuntimeError(f"Unsupported sidecar build platform: {system} ({machine})")


def main():
    name = f"python-sidecar-{target_triple()}"
    target_dir = TAURI_DIR / "target" / "pyinstaller"

    PyInstaller.__main__.run(
        [
            str(SIDECAR_DIR / "sidecar.py"),
            "--clean",
            "--noconfirm",
            "--onefile",
            "--name",
            name,
            "--paths",
            str(SIDECAR_DIR),
            "--distpath",
            str(TAURI_DIR / "binaries"),
            "--workpath",
            str(target_dir / "build"),
            "--specpath",
            str(target_dir),
            "--hidden-import",
            "worker_standalone",
            "--hidden-import",
            "worker2_standalone",
            "--hidden-import",
            "worker3_standalone",
            "--hidden-import",
            "worker4_standalone",
            "--hidden-import",
            "rapidocr_onnxruntime",
            "--hidden-import",
            "pypdfium2",
            "--hidden-import",
            "pypdfium2_raw",
            "--collect-data",
            "rapidocr_onnxruntime",
            "--collect-binaries",
            "onnxruntime",
            "--collect-binaries",
            "pypdfium2_raw",
            "--collect-data",
            "pypdfium2_raw",
            "--exclude-module",
            "pytest",
        ]
    )
    print(f"Sidecar built at {TAURI_DIR / 'binaries' / name}")


if __name__ == "__main__":
    main()
