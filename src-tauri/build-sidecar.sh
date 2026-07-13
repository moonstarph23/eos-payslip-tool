#!/usr/bin/env bash

set -euo pipefail

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "ERROR: Python 3 is not installed or not in PATH." >&2
  exit 1
fi

cd "$(dirname "$0")/sidecar"
rm -rf ../target/sidecar-venv
"$PYTHON" -m venv ../target/sidecar-venv

if [ -x ../target/sidecar-venv/Scripts/python.exe ]; then
  VENV_PYTHON=../target/sidecar-venv/Scripts/python.exe
else
  VENV_PYTHON=../target/sidecar-venv/bin/python
fi

"$VENV_PYTHON" -m pip install --disable-pip-version-check -r requirements-build.lock
"$VENV_PYTHON" build_sidecar.py
