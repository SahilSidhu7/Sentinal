#!/usr/bin/env bash
# Upgrades an installed `sentinal` to the latest release. The installer is
# idempotent — re-running it downloads the newest binary and replaces the one on
# your PATH — so this is just a thin, memorable wrapper around it. `sentinal
# upgrade` does the same thing once the CLI is on PATH.
#
#   ./scripts/upgrade.sh
#   # or: curl -fsSL https://raw.githubusercontent.com/SahilSidhu7/Sentinal/main/scripts/install.sh | bash
#
# Pass through SENTINAL_VERSION / SENTINAL_INSTALL_METHOD to pin a version or use
# the .deb (they're read by install.sh).
set -euo pipefail

INSTALL_URL="https://raw.githubusercontent.com/SahilSidhu7/Sentinal/main/scripts/install.sh"

# Prefer a local checkout's installer if this script is running from one;
# otherwise fetch it (covers `curl | bash` and packaged installs).
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-/dev/null}")" 2>/dev/null && pwd || true)"
if [ -n "$HERE" ] && [ -f "$HERE/install.sh" ]; then
  exec bash "$HERE/install.sh"
fi
exec bash -c "curl -fsSL '$INSTALL_URL' | bash"
