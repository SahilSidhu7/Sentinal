#!/usr/bin/env bash
# Installs VibeSentinel (sentinal CLI + /model + /backend scanner + /dashboard
# static build) on a Linux server. Idempotent — safe to re-run.
#
# Usage:
#   git clone https://github.com/SahilSidhu7/Sentinal.git && cd Sentinal
#   ./scripts/install.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> VibeSentinel install (repo: $REPO_ROOT)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 not found. Install Python 3.11+ first." >&2
  exit 1
fi

PYVER="$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
echo "==> python3 found: $PYVER"

if ! command -v docker >/dev/null 2>&1; then
  echo "warning: docker not found on PATH — 'sentinal run'/'sentinal start' launch containers and need it. Install Docker before running targets." >&2
elif [ "$(id -u)" -ne 0 ] && ! id -nG "$USER" | grep -qw docker; then
  echo "warning: $USER isn't in the 'docker' group yet — 'sentinal run'/'sentinal start' will fail with" >&2
  echo "  'permission denied ... docker.sock' until you fix this (once):" >&2
  echo "      sudo usermod -aG docker $USER && newgrp docker" >&2
  echo "  (log out and back in if 'newgrp' doesn't pick it up). Don't run sentinal itself under sudo —" >&2
  echo "  that resets PATH and breaks the venv." >&2
fi

echo "==> creating venv at .venv"
if ! python3 -m venv .venv 2>/tmp/sentinal-venv-error.$$; then
  cat /tmp/sentinal-venv-error.$$ >&2
  rm -f /tmp/sentinal-venv-error.$$
  echo "" >&2
  echo "error: couldn't create the venv — Ubuntu/Debian's python3 often ships without the venv module." >&2
  echo "Try: sudo apt install python3-venv    (or python3.<minor>-venv for your exact version), then re-run this script." >&2
  exit 1
fi
rm -f /tmp/sentinal-venv-error.$$
# shellcheck disable=SC1091
source .venv/bin/activate
python3 -m pip install --upgrade pip --quiet  # `pip install --upgrade pip` can fail on some platforms (pip can't overwrite its own running executable) -- `python -m pip` doesn't have that problem

echo "==> installing model + backend + cli (editable)"
pip install -e ./model --quiet
pip install -e ./backend --quiet
pip install -e ./cli --quiet

echo "==> exporting ONNX embedding model (needed for detection; skips gracefully if offline)"
if ! (cd model && python scripts/export_onnx_model.py); then
  echo "warning: ONNX export failed (no network?) — re-run 'python model/scripts/export_onnx_model.py' once you have connectivity. Startup scanning and CLI commands still work without it." >&2
fi

if command -v npm >/dev/null 2>&1; then
  echo "==> building dashboard static assets"
  (cd dashboard && npm ci --silent && npm run build --silent) || \
    echo "warning: dashboard build failed — 'sentinal run' will still serve the JSON API on its status port, just without the UI." >&2
else
  echo "warning: npm not found — dashboard UI won't be built. Install Node.js 18+ and re-run this script, or run 'npm ci && npm run build' in ./dashboard manually." >&2
fi

echo ""
echo "==> install complete."
echo ""
echo "Activate the environment in new shells with:"
echo "    source $REPO_ROOT/.venv/bin/activate"
echo ""
echo "Then, from your app's directory:"
echo "    sentinal start --port 8080:8080"
echo ""
echo "The dashboard + JSON API are served together on http://<this-host>:8765 once 'sentinal start' is going."
echo "Upgrade later with: sentinal upgrade   (or ./scripts/upgrade.sh)"
