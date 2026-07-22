"""Regex-based secret detection over a mounted target directory (spec Module 1).

Entropy scoring is intentionally skipped for v0: known-shape regexes (cloud
key formats, PEM headers, common token prefixes) have a far lower
false-positive rate than raw Shannon entropy over arbitrary strings, and a
false "secret found" on every startup scan trains operators to ignore real
ones. Entropy-based fallback is a documented future addition, not a silent
gap — see docs/VULNERABILITY_CHECKLIST.md.
"""
from __future__ import annotations

import re
from pathlib import Path

MAX_FILE_BYTES = 2_000_000  # skip anything bigger; secrets don't hide in multi-MB blobs
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

# (name, severity, compiled pattern) — pattern must have zero or one capture group
_PATTERNS = [
    ("aws_access_key_id", "critical", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws_secret_access_key", "critical", re.compile(r"aws_secret_access_key\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?", re.IGNORECASE)),
    ("private_key", "critical", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----")),
    ("github_token", "critical", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("slack_token", "high", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("generic_api_key", "high", re.compile(r"(?:api[_-]?key|secret[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", re.IGNORECASE)),
    ("hardcoded_password", "medium", re.compile(r"\bpassword\s*[:=]\s*['\"][^'\"\s]{4,}['\"]", re.IGNORECASE)),
    ("jwt_looking_token", "medium", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
]

_ENV_FILE_NAMES = {".env", ".env.local", ".env.production", ".env.development"}


def scan_directory(root: str | Path) -> list[dict]:
    """Returns raw hits as dicts: {type, severity, title, description, path}.

    Caller (scanner.py) converts these into Finding objects with a shared
    detected_at timestamp — this module has no wall-clock dependency so it
    can be unit tested deterministically.
    """
    root = Path(root)
    if not root.exists():
        return []

    hits: list[dict] = []
    for path in _iter_files(root):
        if path.name in _ENV_FILE_NAMES:
            hits.append({
                "type": "secret",
                "severity": "low",
                "title": f"{path.name} file present in mounted volume",
                "description": f"{path.relative_to(root)} may contain live credentials — verify it's not bind-mounted read-accessible beyond this container.",
                "path": str(path.relative_to(root)),
            })

        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(errors="ignore")
        except OSError:
            continue

        for name, severity, pattern in _PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            hits.append({
                "type": "secret",
                "severity": severity,
                "title": f"Possible {name.replace('_', ' ')} in {path.name}",
                "description": f"Pattern match for {name} in {path.relative_to(root)} — rotate the credential if real, then remove it from source.",
                "path": str(path.relative_to(root)),
            })

    return hits


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path
