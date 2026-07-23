#!/usr/bin/env bash
# Wraps the already-built dist/sentinal binary into a Debian package.
# Run build_binary.sh first.
#
#   ./packaging/build_deb.sh <version> [arch]
# e.g. ./packaging/build_deb.sh 0.1.0 amd64
set -euo pipefail

VERSION="${1:?usage: build_deb.sh <version> [arch]}"
ARCH="${2:-amd64}"   # amd64 (x86_64) or arm64 (aarch64)

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/dist/sentinal"
[ -f "$BIN" ] || { echo "error: $BIN not found — run packaging/build_binary.sh first" >&2; exit 1; }

STAGE="$ROOT/dist/deb/sentinal_${VERSION}_${ARCH}"
rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/bin"
install -m0755 "$BIN" "$STAGE/usr/bin/sentinal"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: sentinal
Version: ${VERSION}
Section: admin
Priority: optional
Architecture: ${ARCH}
Maintainer: Sarthak Khurana <sarthakkhurana201@gmail.com>
Recommends: docker.io
Description: VibeSentinel security monitoring agent (sentinel-agent CLI)
 Watches a container or target, runs a startup vulnerability scan, detects live
 attacks locally (Drain3 + ONNX embeddings + Isolation Forest, no LLM), serves a
 local dashboard, and coordinates opt-in IP bans. Self-contained: bundles its own
 Python runtime, ML model, and dashboard UI.
EOF

OUT="$ROOT/dist/sentinal_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT"
echo "==> built $OUT"
