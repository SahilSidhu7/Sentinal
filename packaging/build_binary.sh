#!/usr/bin/env bash
# Builds the self-contained one-file `sentinal` Linux binary into dist/sentinal.
#
# MUST run on Linux (the binary is platform-specific — a Linux build only runs
# on Linux). CI does this on ubuntu-latest; to build locally you need a Linux
# box or container with Python 3.11, Node 18+, and network access.
#
#   ./packaging/build_binary.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> installing python packages (model + backend + cli) + PyInstaller"
python -m pip install --upgrade pip
python -m pip install ./model ./backend ./cli pyinstaller

echo "==> building dashboard static assets"
if ! command -v npm >/dev/null 2>&1; then
  echo "error: npm not found — need Node.js 18+ to build the dashboard UI." >&2
  exit 1
fi
(cd dashboard && npm ci && npm run build)

echo "==> exporting ONNX embedding model (needs network + optimum; build-box only)"
python -m pip install "optimum[onnxruntime]>=1.17"
python model/scripts/export_onnx_model.py

echo "==> running PyInstaller"
rm -rf dist/sentinal build/pyi
pyinstaller packaging/sentinal.spec --distpath dist --workpath build/pyi --noconfirm

if [ ! -f dist/sentinal ]; then
  echo "error: PyInstaller did not produce dist/sentinal" >&2
  exit 1
fi
chmod +x dist/sentinal
echo "==> built dist/sentinal ($(du -h dist/sentinal | cut -f1))"
echo "    smoke test: ./dist/sentinal --version"
