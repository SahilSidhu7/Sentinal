"""Locate vibesentinel_core's data files across a source checkout vs a frozen
binary — mirrors sentinal._resources / vibesentinel_model._resources.

Three read-only assets the hosted platform needs on the *host* (not inside the
env container): the built dashboard UI to serve, the env-image build context
(to `docker build` the environment image on first run), and the demo scripts
(`docker cp`'d into a demo project). From a source checkout these sit next to
this package / at the repo root; in the PyInstaller binary they're extracted
under `sys._MEIPASS`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def bundle_root() -> Path:
    override = os.environ.get("SENTINAL_BUNDLE_DIR")
    if override:
        return Path(override)
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # backend/vibesentinel_core/_resources.py -> repo root
    return Path(__file__).resolve().parents[2]


def _pkg_data(name: str) -> Path:
    """env_image / demo_assets: next to this module in a source checkout,
    under <bundle>/vibesentinel_core/<name> when frozen (see sentinal.spec)."""
    if is_frozen():
        return bundle_root() / "vibesentinel_core" / name
    return Path(__file__).resolve().parent / name


def env_image_dir() -> Path:
    return _pkg_data("env_image")


def demo_assets_dir() -> Path:
    return _pkg_data("demo_assets")


def dashboard_dist() -> Path:
    override = os.environ.get("SENTINAL_DASHBOARD_DIST")
    if override:
        return Path(override)
    return bundle_root() / "dashboard" / "dist"
