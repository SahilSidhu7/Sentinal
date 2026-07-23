#!/usr/bin/env bash
# Pulls the latest VibeSentinel code and reinstalls. Thin wrapper around the
# same steps `sentinal upgrade` runs — use this one if the venv isn't active
# yet or `sentinal` isn't on PATH.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -d .git ]; then
  echo "error: $REPO_ROOT isn't a git checkout — can't self-upgrade." >&2
  exit 1
fi

echo "==> pulling latest"
git pull

if [ ! -d .venv ]; then
  echo "error: no .venv found — run ./scripts/install.sh first." >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> reinstalling model + backend + cli (editable)"
pip install --upgrade -e ./model --quiet
pip install --upgrade -e ./backend --quiet
pip install --upgrade -e ./cli --quiet

if command -v npm >/dev/null 2>&1; then
  echo "==> rebuilding dashboard"
  (cd dashboard && npm ci --silent && npm run build --silent) || \
    echo "warning: dashboard build failed — see npm output above." >&2
fi

# Re-link in case the venv was recreated since install (the symlink target
# path itself doesn't change, but this is idempotent and cheap either way).
if [ -w /usr/local/bin ]; then
  BIN_DIR="/usr/local/bin"
else
  BIN_DIR="$HOME/.local/bin"
  mkdir -p "$BIN_DIR"
fi
ln -sf "$REPO_ROOT/.venv/bin/sentinal" "$BIN_DIR/sentinal"

echo "==> upgraded to $(git rev-parse --short HEAD)"
