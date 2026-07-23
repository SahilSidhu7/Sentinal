"""LiveMonitor: bridges a project's *server terminal* output to /model.

The server terminal's raw PTY bytes are teed here. We strip terminal control
sequences, split into lines, and score them with a per-project LogPipeline
(seeded from the shipped `nginx` model so detection is live from the first
request, no cold-start). Anomalies are pushed to every subscriber queue — the
alerts websocket drains them to the dashboard's live feed.

The pipeline is CPU-bound (ONNX embed + Isolation Forest), so detect() runs in
a thread executor and never blocks the event loop.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time

logger = logging.getLogger("vibesentinel_core.monitor")

# CSI/OSC/APC and other escape sequences the shell echoes — noise to the model.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[]P^_].*?(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")
_SEED_MODEL = "nginx"
# Lines shorter than this are almost always prompt fragments / keystroke echo,
# not real log records — skip them to keep the false-positive rate sane.
_MIN_LINE_LEN = 12
# A PTY tap sees the interactive shell too, not just the server's output: the
# prompt + the command the user typed land on the same line (e.g.
# `root@abc123:~# python3 server.py`). Those aren't log records — scoring them
# against a log-trained model is pure false positives, so drop anything that
# looks like a `user@host:path#`/`$` prompt line.
_SHELL_PROMPT_RE = re.compile(r"^\S+@\S+:.*[#$]")
# A model seeded from a pretrained dataset flags the first few unseen templates
# of a *different* target as anomalous until enough of its own normal traffic
# has been observed (cold Drain3 state + seed-vs-target drift). This mirrors the
# CLI's baseline warmup: for the first N scored lines we suppress ML-only
# anomalies — but never signature attacks, which must fire from request #1.
_WARMUP_LINES = 25


def _clean(text: str) -> str:
    return _ANSI_RE.sub("", text).replace("\r", "")


def _is_noise(line: str) -> bool:
    stripped = line.strip()
    return len(stripped) < _MIN_LINE_LEN or bool(_SHELL_PROMPT_RE.match(stripped))


class LiveMonitor:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self._pipeline = None
        self._enabled = False
        self._buffer = ""
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
        self._warmup_remaining = _WARMUP_LINES
        self.alert_count = 0
        self._init_pipeline()

    def _init_pipeline(self) -> None:
        try:
            from vibesentinel_model import LogPipeline
        except Exception:
            logger.warning("vibesentinel_model not installed — live monitoring disabled for %s", self.project_id)
            return
        try:
            pipeline = LogPipeline(self.project_id)
            pipeline.seed_from_pretrained(_SEED_MODEL)
            self._pipeline = pipeline
            self._enabled = True
            logger.info("monitor for %s seeded from %r — detection live", self.project_id, _SEED_MODEL)
        except Exception:
            logger.exception("failed to init pipeline for %s — monitoring disabled", self.project_id)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    async def feed_bytes(self, chunk: bytes) -> None:
        """Called with raw server-terminal output. Extracts complete lines and
        scores them; a partial trailing line is held until its newline lands."""
        if not self._enabled:
            return
        self._buffer += _clean(chunk.decode("utf-8", errors="replace"))
        if "\n" not in self._buffer:
            return
        *lines, self._buffer = self._buffer.split("\n")
        candidates = [ln for ln in lines if not _is_noise(ln)]
        if candidates:
            await self._score(candidates)

    async def _score(self, lines: list[str]) -> None:
        async with self._lock:  # one detect() at a time per project
            try:
                results = await asyncio.to_thread(self._pipeline.detect, lines)
            except Exception:
                logger.exception("detect() failed for %s — disabling monitor", self.project_id)
                self._enabled = False
                return
        for line, r in zip(lines, results):
            warming = self._warmup_remaining > 0
            if warming:
                self._warmup_remaining -= 1
            if r.flag != -1:
                continue
            is_attack = bool(r.matched_signature)
            if warming and not is_attack:
                continue  # cold-start ML false positive — suppress, keep attacks
            await self._emit({
                "type": "attack" if is_attack else "anomaly",
                "project_id": self.project_id,
                "template": r.template,
                "severity_score": round(float(r.severity_score), 3),
                "matched_signature": r.matched_signature,
                "line": line[:500],
                "ts": time.time(),
            })

    async def _emit(self, alert: dict) -> None:
        self.alert_count += 1
        for q in list(self._subscribers):
            try:
                q.put_nowait(alert)
            except asyncio.QueueFull:
                pass  # a slow/absent dashboard shouldn't back up the monitor
