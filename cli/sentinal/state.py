"""In-memory agent state: the single source of truth `local_api.py` serves to
/dashboard and `app.py`'s scan/detect loop writes into. One instance per
running `sentinal run` process — not persisted, not shared across targets.

This is the thin-localhost-status-site path (spec §8: "/dashboard — served
by /cli, for single-box operators without the full /backend running"), not
a replacement for the core backend's SQLite-backed findings table.
"""
from __future__ import annotations

import asyncio
import itertools
import threading
import time
from dataclasses import dataclass, field

_id_counter = itertools.count(1)


def _next_id(prefix: str) -> str:
    return f"{prefix}-{next(_id_counter)}"


DEFAULT_SETTINGS = {
    "operator_name": "",
    "email": "",
    "notify_critical_alerts": True,
    "notify_log_summaries": False,
}


@dataclass
class AgentState:
    target_id: str
    findings: list[dict] = field(default_factory=list)
    attacks: list[dict] = field(default_factory=list)
    settings: dict = field(default_factory=lambda: dict(DEFAULT_SETTINGS))
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _subscribers: list[asyncio.Queue] = field(default_factory=list)
    _loop: asyncio.AbstractEventLoop | None = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def set_findings(self, findings: list[dict]) -> None:
        with self._lock:
            self.findings = findings
        self._broadcast({"kind": "findings_replaced", "count": len(findings)})

    def add_attack(self, attack: dict) -> None:
        attack.setdefault("id", _next_id("a"))
        attack.setdefault("detected_at", _iso_now())
        with self._lock:
            self.attacks.insert(0, attack)
            self.attacks = self.attacks[:200]
        self._broadcast(attack)

    def resolve_attack(self, attack_id: str, action: str) -> bool:
        with self._lock:
            for a in self.attacks:
                if a.get("id") == attack_id:
                    a["status"] = action
                    return True
        return False

    def score(self) -> dict:
        with self._lock:
            findings = list(self.findings)
        deductions = {"critical": 30, "high": 15, "medium": 7, "low": 3, "safe": 0}
        open_findings = [f for f in findings if f.get("status", "open") == "open"]
        score = max(0, 100 - sum(deductions.get(f.get("severity"), 0) for f in open_findings))
        return {
            "score": score,
            "issues_open": len(open_findings),
            "metrics": [],
        }

    def _broadcast(self, event: dict) -> None:
        if self._loop is None:
            return
        for queue in list(self._subscribers):
            self._loop.call_soon_threadsafe(queue.put_nowait, event)

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
