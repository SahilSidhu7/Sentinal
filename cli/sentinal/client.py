"""HTTP client for the agent-facing core backend API (spec §6, §7)."""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class CoreClient:
    """Talks to `/agent/register`, `/agent/events/batch`, `/agent/heartbeat`.

    Only structured findings/events cross the wire — raw log lines never do.
    """

    def __init__(self, backend_url: str, token: str | None = None, timeout: float = 10.0):
        self.backend_url = backend_url.rstrip("/")
        self.token = token
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def register(self, target_id: str) -> str:
        """Registers this target with core, returns the scoped deployment token."""
        resp = httpx.post(
            f"{self.backend_url}/agent/register",
            json={"target_id": target_id},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()["token"]

    def trigger_scan(self, target_id: str) -> dict:
        """POST /targets/{id}/scan — runs the backend's Scanner (Module 1) and
        returns its findings + score. CLI blocks container startup on the
        result rather than duplicating scanner logic locally.
        """
        resp = httpx.post(
            f"{self.backend_url}/targets/{target_id}/scan",
            headers=self._headers(),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def heartbeat(self, target_id: str) -> None:
        httpx.post(
            f"{self.backend_url}/agent/heartbeat",
            json={"target_id": target_id},
            headers=self._headers(),
            timeout=self._timeout,
        )

    def send_events(self, target_id: str, events: list[dict]) -> None:
        if not events:
            return
        resp = httpx.post(
            f"{self.backend_url}/agent/events/batch",
            json={"target_id": target_id, "events": events},
            headers=self._headers(),
            timeout=self._timeout,
        )
        resp.raise_for_status()
