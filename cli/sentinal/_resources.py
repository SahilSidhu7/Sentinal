"""Locate CLI-side data files across a source checkout vs a frozen binary.

Mirrors vibesentinel_model._resources, kept separate so /cli doesn't have to
import /model just to find its own bundled dashboard build. The dashboard's
static `dist/` is a read-only shipped artifact: from a source checkout it's the
sibling `dashboard/dist/` at the repo root; in the PyInstaller binary it's
extracted under `sys._MEIPASS/dashboard/dist`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """True when running inside a PyInstaller-built binary."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def bundle_root() -> Path:
    """Base dir shipped read-only assets live under (bundle when frozen, repo
    root from a source checkout). Override with `$SENTINAL_BUNDLE_DIR`."""
    override = os.environ.get("SENTINAL_BUNDLE_DIR")
    if override:
        return Path(override)
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # cli/sentinal/_resources.py -> repo root
    return Path(__file__).resolve().parents[2]


def dashboard_dist() -> Path:
    """Directory of the built dashboard UI to serve, honoring an explicit
    `$SENTINAL_DASHBOARD_DIST` override."""
    override = os.environ.get("SENTINAL_DASHBOARD_DIST")
    if override:
        return Path(override)
    return bundle_root() / "dashboard" / "dist"
