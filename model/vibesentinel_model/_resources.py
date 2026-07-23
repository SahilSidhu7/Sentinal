"""Locate data files across the three ways this code runs.

1. From a source checkout (`pip install -e ./model`): artifacts sit next to
   the package at `model/artifacts/`, resolved off `__file__`.
2. From a PyInstaller one-file binary (`sentinal` release): the shipped,
   read-only artifacts are extracted to `sys._MEIPASS` at startup.
3. Under explicit env overrides (tests, custom deployments).

A hard split matters once the code ships as a frozen binary: the bundle dir
is read-only/ephemeral (recreated per run in one-file mode), so anything the
agent *writes* per target — a target's own trained Isolation Forest, its live
Drain3 state — must go to a persistent, user-writable data dir instead.
Read-only shipped seeds (pretrained dataset models, the ONNX embedding model,
`drain3_config.ini`) come from the bundle; per-target state goes to the data
dir. See anomaly.py / log_parser.py / embedder.py for who uses which.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """True when running inside a PyInstaller-built binary."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def bundle_root() -> Path:
    """Base dir the shipped, read-only artifacts live under.

    - `$SENTINAL_BUNDLE_DIR` if set (must contain an `artifacts/` subdir).
    - `sys._MEIPASS` when frozen (PyInstaller extraction dir).
    - the package's parent (`.../model`) when run from a source checkout.
    """
    override = os.environ.get("SENTINAL_BUNDLE_DIR")
    if override:
        return Path(override)
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def bundled_artifacts_dir() -> Path:
    """Where read-only shipped artifacts (pretrained models, ONNX, drain3
    seeds) live — inside the bundle when frozen, `model/artifacts/` from source."""
    return bundle_root() / "artifacts"


def data_dir() -> Path:
    """User-writable dir for per-target state that must survive across runs.

    `$SENTINAL_DATA_DIR` > `$XDG_DATA_HOME/sentinal` > `~/.local/share/sentinal`.
    Not created here — callers mkdir the specific subdir they need.
    """
    override = os.environ.get("SENTINAL_DATA_DIR")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "sentinal"
