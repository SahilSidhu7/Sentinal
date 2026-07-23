#!/usr/bin/env bash
# One-line installer for the `sentinal` CLI (VibeSentinel sentinel-agent).
#
#   curl -fsSL https://raw.githubusercontent.com/SahilSidhu7/Sentinal/main/scripts/install.sh | bash
#
# Downloads the self-contained `sentinal` binary for this machine's architecture
# from the latest GitHub Release and puts it on your PATH. No repo clone, no
# Python, no virtualenv — it behaves like any other installed command.
# Re-running it upgrades in place (so is `sentinal upgrade`).
#
# Environment overrides:
#   SENTINAL_VERSION=0.1.0    install a specific version instead of latest
#   SENTINAL_INSTALL_METHOD=deb   install via the .deb package (needs dpkg + sudo)
#   SENTINAL_BIN_DIR=/path     install dir for the raw-binary method
set -euo pipefail

REPO="SahilSidhu7/Sentinal"
METHOD="${SENTINAL_INSTALL_METHOD:-binary}"

say()  { printf '==> %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }

# --- platform / arch -------------------------------------------------------
[ "$(uname -s)" = "Linux" ] || die "sentinal ships a Linux binary only — this is $(uname -s). On Windows use WSL."

case "$(uname -m)" in
  x86_64|amd64)   ARCH="x86_64"; DEBARCH="amd64" ;;
  aarch64|arm64)  ARCH="aarch64"; DEBARCH="arm64" ;;
  *) die "unsupported architecture: $(uname -m) (only x86_64 and aarch64 are built)" ;;
esac

command -v curl >/dev/null 2>&1 || die "curl not found — install curl and re-run."

# --- resolve version -------------------------------------------------------
# GitHub redirects /releases/latest/download/<asset> to the newest release, so
# the raw-binary path needs no version. The .deb filename embeds the version,
# so resolve it from the /releases/latest redirect target when not pinned.
resolve_latest_version() {
  local url
  url="$(curl -fsSLI -o /dev/null -w '%{url_effective}' "https://github.com/${REPO}/releases/latest")" \
    || die "couldn't reach GitHub Releases — check connectivity, or set SENTINAL_VERSION."
  local tag="${url##*/tag/}"
  [ "$tag" != "$url" ] && [ -n "$tag" ] || die "no published release found for ${REPO} yet."
  printf '%s' "${tag#v}"
}

# --- sudo helper -----------------------------------------------------------
maybe_sudo() {
  if [ "$(id -u)" -eq 0 ]; then "$@"; return; fi
  if command -v sudo >/dev/null 2>&1; then sudo "$@"; return; fi
  die "need root to $* — run as root or install sudo."
}

install_binary() {
  local asset="sentinal-linux-${ARCH}"
  local url
  if [ -n "${SENTINAL_VERSION:-}" ]; then
    url="https://github.com/${REPO}/releases/download/v${SENTINAL_VERSION}/${asset}"
  else
    url="https://github.com/${REPO}/releases/latest/download/${asset}"
  fi

  local tmp
  tmp="$(mktemp)"
  say "downloading ${asset} ..."
  curl -fSL --progress-bar "$url" -o "$tmp" || die "download failed: $url"
  chmod +x "$tmp"

  # Prefer a system-wide dir; fall back to a per-user one with a PATH note.
  local bin_dir="${SENTINAL_BIN_DIR:-}"
  if [ -z "$bin_dir" ]; then
    if [ -w /usr/local/bin ] || [ "$(id -u)" -eq 0 ]; then
      bin_dir="/usr/local/bin"
    elif command -v sudo >/dev/null 2>&1; then
      bin_dir="/usr/local/bin"
    else
      bin_dir="$HOME/.local/bin"
    fi
  fi
  mkdir -p "$bin_dir" 2>/dev/null || maybe_sudo mkdir -p "$bin_dir"

  if [ -w "$bin_dir" ]; then
    install -m0755 "$tmp" "$bin_dir/sentinal"
  else
    maybe_sudo install -m0755 "$tmp" "$bin_dir/sentinal"
  fi
  rm -f "$tmp"
  say "installed sentinal -> $bin_dir/sentinal"

  if [[ ":$PATH:" != *":$bin_dir:"* ]]; then
    warn "$bin_dir isn't on your PATH — add this to your shell rc and open a new shell:"
    printf '    export PATH="%s:$PATH"\n' "$bin_dir" >&2
  fi
}

install_deb() {
  command -v dpkg >/dev/null 2>&1 || die "SENTINAL_INSTALL_METHOD=deb needs dpkg (Debian/Ubuntu)."
  local version="${SENTINAL_VERSION:-$(resolve_latest_version)}"
  local asset="sentinal_${version}_${DEBARCH}.deb"
  local url="https://github.com/${REPO}/releases/download/v${version}/${asset}"
  local tmp
  tmp="$(mktemp --suffix=.deb)"
  say "downloading ${asset} ..."
  curl -fSL --progress-bar "$url" -o "$tmp" || die "download failed: $url"
  say "installing package (dpkg) ..."
  maybe_sudo dpkg -i "$tmp" || maybe_sudo apt-get -f install -y
  rm -f "$tmp"
  say "installed sentinal (deb)"
}

case "$METHOD" in
  binary) install_binary ;;
  deb)    install_deb ;;
  *) die "unknown SENTINAL_INSTALL_METHOD=$METHOD (use 'binary' or 'deb')" ;;
esac

# --- post-install checks ---------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  warn "docker not found — 'sentinal run'/'sentinal start' launch containers and need it. Install Docker Engine before running a target."
elif [ "$(id -u)" -ne 0 ] && ! id -nG "$USER" 2>/dev/null | grep -qw docker; then
  warn "$USER isn't in the 'docker' group yet — 'sentinal run' will fail on docker.sock until you fix this once:"
  printf '    sudo usermod -aG docker %s && newgrp docker\n' "$USER" >&2
fi

echo ""
say "done. Verify:  sentinal --version"
echo ""
echo "From inside your app's own directory:"
echo "    sentinal start --port 8080:8080"
echo ""
echo "That builds/launches your container, runs the startup scan, and serves the"
echo "dashboard + JSON API on http://<this-host>:8765. Control it with"
echo "'sentinal logs|scan|status|stop --target-id ...'. Upgrade later with 'sentinal upgrade'."
