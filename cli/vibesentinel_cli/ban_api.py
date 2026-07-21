"""Local ban-action API (spec §7): agent-local only, never core-initiated host-wide.

Core can only request a ban through this narrow, agent-scoped endpoint —
scoped to this agent's own network namespace, for IPs core has already flagged.
"""
from __future__ import annotations

import logging
import time

from fastapi import FastAPI
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BanRequest(BaseModel):
    ip: str
    ttl: int  # seconds


class BanRecord(BaseModel):
    ip: str
    ttl: int
    banned_at: float
    expires_at: float


def apply_ban(ip: str, ttl: int) -> None:
    """Executes the ban in this agent's own network namespace.

    Stub: real implementation shells out to iptables/nftables scoped to this
    container/host only. Kept as a no-op hook so the API contract is stable
    while the underlying enforcement mechanism is finished.
    """
    logger.info("ban applied ip=%s ttl=%ds (stub — no firewall rule written)", ip, ttl)


def create_app() -> FastAPI:
    app = FastAPI(title="vibesentinel-agent local ban API")
    active_bans: dict[str, BanRecord] = {}

    @app.post("/agent/actions/ban")
    def ban(req: BanRequest) -> BanRecord:
        now = time.time()
        record = BanRecord(ip=req.ip, ttl=req.ttl, banned_at=now, expires_at=now + req.ttl)
        active_bans[req.ip] = record
        apply_ban(req.ip, req.ttl)
        return record

    @app.get("/agent/actions/bans")
    def list_bans() -> list[BanRecord]:
        return list(active_bans.values())

    return app
