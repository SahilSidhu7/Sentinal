"""Local ban-action API (spec §7): agent-local only, never core-initiated host-wide.

Backend coordinates an IP-attack finding, then calls this narrow endpoint on
the agent — scoped to this agent's own container's network namespace. Bans
are TTL-based and auto-reversed.
"""
from __future__ import annotations

import logging
import threading
import time

from fastapi import FastAPI
from pydantic import BaseModel

from sentinal.container import ContainerRuntime

logger = logging.getLogger(__name__)


class BanRequest(BaseModel):
    ip: str
    ttl: int  # seconds


class BanRecord(BaseModel):
    ip: str
    ttl: int
    banned_at: float
    expires_at: float


def apply_ban(runtime: ContainerRuntime, container_id: str, ip: str, ttl: int) -> None:
    """Drops the IP inside the monitored container's own network namespace,
    then schedules the matching unban after `ttl` seconds (reversible)."""
    result = runtime.exec(container_id, ["iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"])
    if result.returncode != 0:
        logger.warning("ban ip=%s container=%s failed: %s", ip, container_id, result.stderr.strip())
        return

    logger.info("banned ip=%s container=%s ttl=%ds", ip, container_id, ttl)
    threading.Timer(ttl, _unban, args=(runtime, container_id, ip)).start()


def _unban(runtime: ContainerRuntime, container_id: str, ip: str) -> None:
    result = runtime.exec(container_id, ["iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"])
    if result.returncode != 0:
        logger.warning("unban ip=%s container=%s failed: %s", ip, container_id, result.stderr.strip())
    else:
        logger.info("unbanned ip=%s container=%s (ttl expired)", ip, container_id)


def create_app(container_id: str, runtime: ContainerRuntime | None = None) -> FastAPI:
    app = FastAPI(title="sentinal agent local ban API")
    runtime = runtime or ContainerRuntime()
    active_bans: dict[str, BanRecord] = {}

    @app.post("/agent/actions/ban")
    def ban(req: BanRequest) -> BanRecord:
        now = time.time()
        record = BanRecord(ip=req.ip, ttl=req.ttl, banned_at=now, expires_at=now + req.ttl)
        active_bans[req.ip] = record
        apply_ban(runtime, container_id, req.ip, req.ttl)
        return record

    @app.get("/agent/actions/bans")
    def list_bans() -> list[BanRecord]:
        return list(active_bans.values())

    return app
