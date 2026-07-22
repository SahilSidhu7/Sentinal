"""Dependency CVE lookup via OSV.dev batch API (spec Module 1).

Needs outbound network access. Per CLAUDE.md §13: degrade to an
"unknown, network unavailable" finding rather than failing the scan.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
REQUEST_TIMEOUT = 8.0


def _parse_requirements_txt(text: str) -> list[tuple[str, str, str]]:
    packages = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = re.match(r"^([A-Za-z0-9_.\-]+)\s*==\s*([A-Za-z0-9_.\-]+)", line)
        if match:
            packages.append(("PyPI", match.group(1), match.group(2)))
    return packages


def _parse_package_json(text: str) -> list[tuple[str, str, str]]:
    packages = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return packages
    for section in ("dependencies", "devDependencies"):
        for name, version in (data.get(section) or {}).items():
            version = str(version).lstrip("^~=v")
            if re.match(r"^\d", version):
                packages.append(("npm", name, version))
    return packages


_MANIFESTS = {
    "requirements.txt": _parse_requirements_txt,
    "package.json": _parse_package_json,
}


def find_manifests(root: str | Path) -> list[tuple[str, str, str]]:
    """Walks `root` for known manifest files, returns (ecosystem, name, version) tuples."""
    root = Path(root)
    if not root.exists():
        return []

    packages: list[tuple[str, str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.name not in _MANIFESTS:
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        packages.extend(_MANIFESTS[path.name](text))
    return packages


def check_dependencies(root: str | Path) -> list[dict]:
    packages = find_manifests(root)
    if not packages:
        return []

    queries = [
        {"package": {"name": name, "ecosystem": eco}, "version": version}
        for eco, name, version in packages
    ]

    try:
        resp = httpx.post(OSV_BATCH_URL, json={"queries": queries}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except (httpx.HTTPError, OSError):
        return [{
            "type": "dependency_cve",
            "severity": "safe",
            "title": f"Dependency CVE check skipped ({len(packages)} package(s) found)",
            "description": "OSV.dev unreachable — network unavailable. Dependency versions were not checked against known CVEs this run.",
        }]

    hits: list[dict] = []
    for (eco, name, version), result in zip(packages, results):
        vulns = result.get("vulns") or []
        if not vulns:
            continue
        ids = ", ".join(v["id"] for v in vulns[:5])
        hits.append({
            "type": "dependency_cve",
            "severity": "high" if len(vulns) > 1 else "medium",
            "title": f"{name}=={version} has {len(vulns)} known advisory(ies)",
            "description": f"OSV.dev: {ids}{'...' if len(vulns) > 5 else ''} — upgrade {name} past the affected range.",
        })
    return hits
