"""Shared Finding shape — the contract /cli, /dashboard, and (eventually) the
real /backend API all render (spec §5 `findings` table, §8 stable contract).
"""
from __future__ import annotations

from dataclasses import dataclass, field

SEVERITY_DEDUCTION = {
    "critical": 30,
    "high": 15,
    "medium": 7,
    "low": 3,
    "safe": 0,
}

_counter = {"n": 0}


def next_id() -> str:
    _counter["n"] += 1
    return f"f-{_counter['n']}"


@dataclass
class Finding:
    type: str  # e.g. "secret", "docker_misconfig", "dependency_cve", "weak_credential"
    severity: str  # critical | high | medium | low | safe
    title: str
    description: str
    detected_at: str  # ISO8601, set by caller (no wall-clock inside a workflow-safe module)
    id: str = field(default_factory=next_id)
    status: str = "open"
