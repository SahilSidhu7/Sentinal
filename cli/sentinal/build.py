"""Builds a container image directly from a user's app source — the point
being nobody hand-writes `docker build`/`docker run` themselves. If the
source already has a Dockerfile, that's used as-is (never overwritten —
a project's own Dockerfile is often deliberate, e.g. sentinel-demo-app's
seeded misconfigurations exist specifically for the scanner to catch).
Otherwise a Dockerfile is generated from a lightweight stack detection.
"""
from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class BuildError(RuntimeError):
    pass


_PYTHON_ENTRYPOINT_CANDIDATES = ["app.py", "main.py", "wsgi.py", "manage.py"]
_NODE_ENTRYPOINT_CANDIDATES = ["index.js", "server.js", "app.js"]


def _detect_python_entrypoint(path: Path) -> str:
    for name in _PYTHON_ENTRYPOINT_CANDIDATES:
        if (path / name).exists():
            return name
    raise BuildError(
        f"found requirements.txt in {path} but no {_PYTHON_ENTRYPOINT_CANDIDATES} to run — "
        "add one of those, or add your own Dockerfile with a CMD."
    )


def _detect_node_entrypoint(path: Path) -> str:
    package_json = path / "package.json"
    try:
        data = json.loads(package_json.read_text())
    except (OSError, json.JSONDecodeError):
        data = {}
    if "start" in (data.get("scripts") or {}):
        return "__npm_start__"
    for name in _NODE_ENTRYPOINT_CANDIDATES:
        if (path / name).exists():
            return name
    raise BuildError(
        f"found package.json in {path} but no \"start\" script and no {_NODE_ENTRYPOINT_CANDIDATES} — "
        "add one of those, or add your own Dockerfile with a CMD."
    )


def _generate_dockerfile(path: Path) -> str:
    """Returns generated Dockerfile *content* — never touches the user's
    source tree. Detection order: existing Dockerfile (handled by the
    caller before this is reached) -> requirements.txt (Python) ->
    package.json (Node)."""
    if (path / "requirements.txt").exists():
        entrypoint = _detect_python_entrypoint(path)
        logger.info("detected Python app in %s, entrypoint=%s", path, entrypoint)
        return (
            "FROM python:3.11-slim\n"
            "WORKDIR /app\n"
            "COPY requirements.txt .\n"
            "RUN pip install --no-cache-dir -r requirements.txt\n"
            "COPY . .\n"
            f'CMD ["python", "{entrypoint}"]\n'
        )

    if (path / "package.json").exists():
        entrypoint = _detect_node_entrypoint(path)
        logger.info("detected Node app in %s, entrypoint=%s", path, entrypoint)
        cmd = '["npm", "start"]' if entrypoint == "__npm_start__" else f'["node", "{entrypoint}"]'
        return (
            "FROM node:20-slim\n"
            "WORKDIR /app\n"
            "COPY package*.json .\n"
            "RUN npm ci --omit=dev || npm install --omit=dev\n"
            "COPY . .\n"
            f"CMD {cmd}\n"
        )

    raise BuildError(
        f"couldn't detect an app type in {path} (looked for requirements.txt, package.json) — "
        "add a Dockerfile, or one of those manifest files."
    )


def ensure_dockerfile(path: str | Path) -> tuple[Path, Path, bool]:
    """Returns (build_context_dir, dockerfile_path, was_generated).

    If `path` already has a Dockerfile, it's used unmodified. Otherwise a
    Dockerfile is generated into a temp dir (never written into the user's
    source tree) and passed to `docker build -f` against `path` as the
    build context.
    """
    path = Path(path).resolve()
    if not path.is_dir():
        raise BuildError(f"{path} isn't a directory")

    existing = path / "Dockerfile"
    if existing.exists():
        return path, existing, False

    content = _generate_dockerfile(path)
    tmp_dir = Path(tempfile.mkdtemp(prefix="sentinal-build-"))
    generated = tmp_dir / "Dockerfile"
    generated.write_text(content)
    return path, generated, True
