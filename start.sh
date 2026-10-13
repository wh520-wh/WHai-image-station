#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo
echo "  WHai Image Station - AI Image Generator"
echo "  -------------------------------"
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] Python 3 not found. Please install Python 3.10+"
    exit 1
fi

if [ ! -f ".venv/bin/python" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

if [ ! -f ".venv/.deps_installed" ]; then
    echo "[INFO] Installing dependencies..."
    pip install -r requirements.txt -q
    echo "[INFO] Installing project in editable mode..."
    pip install -e . -q
    touch .venv/.deps_installed
fi

echo "[INFO] Starting WHai Image Station..."
echo
python -m src.main
