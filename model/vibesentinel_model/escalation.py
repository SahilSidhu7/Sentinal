"""Sustained, per-source-IP escalation before any response action is considered.

Per-line anomaly flags carry a real false-positive rate (see model/README.md
eval numbers) — never gate a destructive action off a single flagged line.
Gate off a sustained pattern from the same source within a time window
instead. This is what /backend's Auto-Response (Module 7) should call before
recommending — or, for opt-in auto-ban, executing — any action.
"""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass

from .anomaly import DetectionResult

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

SEVERITY_THRESHOLD = 0.7  # per-line: below this, not even "suspicious" — see model/README.md tuning notes
MIN_EVENTS_TO_ESCALATE = 4  # sustained count within window before it's an Attack Event
WINDOW_SECONDS = 300  # spec §4/§6.4 default correlation/escalation window


@dataclass
class AttackEvent:
    source_ip: str
    confidence: float  # 0-1, mean severity across the contributing window
    event_count: int
    first_seen: float
    last_seen: float
    sample_templates: list[str]
    suggested_action: str


def extract_source_ip(raw_line: str) -> str | None:
    match = _IP_RE.search(raw_line)
    return match.group(0) if match else None


def suggest_action(confidence: float, event_count: int) -> str:
    """Graduated response ladder (see model/README.md "Response ladder").

    Escalates from silent logging -> visible friction -> reversible network
    action, and only reaches "ban" at sustained, high-confidence volume — and
    even then it's a recommendation, not an execution (manual-confirm by
    default per spec Module 7; auto-ban stays opt-in and agent-scoped).
    """
    if confidence >= 0.85 and event_count >= 10:
        return "ban_ip"
    if confidence >= 0.7 and event_count >= 6:
        return "rate_limit_and_challenge"
    if confidence >= 0.6:
        return "flag_for_review"
    return "log_only"


class EscalationTracker:
    """Per-target sliding window of anomalous events, keyed by source IP.

    Feed every DetectionResult (with the source IP from the same raw line)
    through observe(); it returns an AttackEvent only once MIN_EVENTS_TO_ESCALATE
    anomalies land from the same IP inside WINDOW_SECONDS.
    """

    def __init__(
        self,
        window_seconds: float = WINDOW_SECONDS,
        min_events: int = MIN_EVENTS_TO_ESCALATE,
        severity_threshold: float = SEVERITY_THRESHOLD,
    ):
        self._window_seconds = window_seconds
        self._min_events = min_events
        self._severity_threshold = severity_threshold
        self._events: dict[str, deque] = {}

    def observe(self, source_ip: str, result: DetectionResult, timestamp: float) -> AttackEvent | None:
        # Gate on severity_score (continuous, calibrated against the training
        # baseline) rather than the binary flag — flag's threshold comes from
        # `contamination`, which is a rough guess and easy to miscalibrate on
        # a small/low-diversity baseline. severity_score is the real signal.
        if result.severity_score < self._severity_threshold:
            return None

        window = self._events.setdefault(source_ip, deque())
        window.append((timestamp, result))
        self._evict_old(window, timestamp)

        if len(window) < self._min_events:
            return None

        confidence = sum(r.severity_score for _, r in window) / len(window)
        return AttackEvent(
            source_ip=source_ip,
            confidence=confidence,
            event_count=len(window),
            first_seen=window[0][0],
            last_seen=window[-1][0],
            sample_templates=[r.template for _, r in list(window)[-3:]],
            suggested_action=suggest_action(confidence, len(window)),
        )

    def _evict_old(self, window: deque, now: float) -> None:
        while window and now - window[0][0] > self._window_seconds:
            window.popleft()
