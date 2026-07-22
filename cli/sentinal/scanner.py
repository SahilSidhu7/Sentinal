"""Lazy access to /backend's vibesentinel_scanner — the startup vulnerability
check (spec Module 1). Degrades to "scan skipped" rather than blocking
container startup if the scanner package isn't installed.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def run_startup_scan(volumes: list[str], env: list[str], docker_inspect: dict | None):
    """volumes: the `host:container[:opts]` strings passed to `docker run -v` —
    only the host-side path is scanned (never reach into the container's own
    filesystem from outside)."""
    try:
        from vibesentinel_scanner import Scanner
    except ImportError:
        logger.warning("vibesentinel_scanner not installed — startup vulnerability scan skipped")
        return None

    host_paths = [v.split(":")[0] for v in volumes]
    try:
        return Scanner().run(root_paths=host_paths, env_pairs=env, docker_inspect=docker_inspect)
    except Exception:
        logger.warning("startup scan failed — proceeding without it", exc_info=True)
        return None
