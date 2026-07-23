"""Thin localhost status API — what /dashboard's src/lib/api.js fetches
against (spec §8: "/dashboard — served by /cli"). Separate from ban_api.py
on purpose: that one is a narrow action endpoint core calls into; this one
is a read/status surface for a human looking at the local dashboard.
"""
from __future__ import annotations

import asyncio
import logging
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sentinal._resources import dashboard_dist
from sentinal.container import ContainerRuntime
from sentinal.state import AgentState

logger = logging.getLogger(__name__)

# Resolved via _resources so it works from a source checkout (sibling
# dashboard/dist), from the frozen binary (bundled under sys._MEIPASS), or via
# a $SENTINAL_DASHBOARD_DIST override — see _resources.dashboard_dist.
DASHBOARD_DIST = dashboard_dist()


_STATE_MAP = {"running": "running", "exited": "stopped", "created": "stopped", "paused": "stopped"}


def _normalize_container(raw: dict) -> dict:
    """`docker ps --format json` fields (ID/Names/State/Status/RunningFor/...)
    -> the shape /dashboard's Containers.jsx renders (id/name/status/image/
    uptime/exit_info/cpu_pct — see mockData.js's mockContainers)."""
    state = (raw.get("State") or "").lower()
    status_text = raw.get("Status", "")
    exited_nonzero = state == "exited" and "(0)" not in status_text
    return {
        "id": raw.get("ID", ""),
        "name": raw.get("Names", ""),
        "image": raw.get("Image", ""),
        "status": "error" if exited_nonzero else _STATE_MAP.get(state, "stopped"),
        "uptime": raw.get("RunningFor") if state == "running" else None,
        "exit_info": status_text if state != "running" else None,
        "cpu_pct": None,  # docker ps has no live stats; would need `docker stats` polling
    }


class SettingsUpdate(BaseModel):
    operator_name: str | None = None
    email: str | None = None
    department: str | None = None
    two_factor_enabled: bool | None = None
    session_timeout_enabled: bool | None = None
    ip_whitelist: str | None = None
    notify_critical_alerts: bool | None = None
    notify_log_summaries: bool | None = None
    notify_marketing: bool | None = None


class LoginRequest(BaseModel):
    password: str


def create_app(state: AgentState, runtime: ContainerRuntime | None = None, admin_password: str = "admin") -> FastAPI:
    app = FastAPI(title="sentinal local status API")
    runtime = runtime or ContainerRuntime()

    # Single-operator, process-local session: one token minted per `sentinal
    # run` process, invalidated on restart. No user table / bcrypt needed —
    # this is a local status site (spec §8), not the core backend's auth.
    session_token = secrets.token_urlsafe(32)

    def require_auth(authorization: str | None = Header(default=None)) -> None:
        if authorization != f"Bearer {session_token}":
            raise HTTPException(status_code=401, detail="not authenticated")

    @app.on_event("startup")
    async def _bind_loop() -> None:
        state.set_event_loop(asyncio.get_running_loop())

    @app.post("/api/auth/login")
    def login(body: LoginRequest) -> dict:
        if not secrets.compare_digest(body.password, admin_password):
            raise HTTPException(status_code=401, detail="incorrect password")
        return {"token": session_token}

    @app.get("/api/auth/verify")
    def verify(_: None = Depends(require_auth)) -> dict:
        return {"ok": True}

    @app.get("/api/score")
    def get_score(_: None = Depends(require_auth)) -> dict:
        return state.score()

    @app.get("/api/findings")
    def get_findings(_: None = Depends(require_auth)) -> list[dict]:
        return state.findings

    @app.get("/api/attacks")
    def get_attacks(_: None = Depends(require_auth)) -> list[dict]:
        return state.attacks

    @app.post("/api/attacks/{attack_id}/{action}")
    def respond_to_attack(attack_id: str, action: str, _: None = Depends(require_auth)) -> dict:
        ok = state.resolve_attack(attack_id, action)
        return {"ok": ok}

    @app.get("/api/settings")
    def get_settings(_: None = Depends(require_auth)) -> dict:
        return state.settings

    @app.post("/api/settings")
    def save_settings(update: SettingsUpdate, _: None = Depends(require_auth)) -> dict:
        state.settings.update({k: v for k, v in update.model_dump().items() if v is not None})
        return state.settings

    @app.get("/api/containers")
    def get_containers(_: None = Depends(require_auth)) -> list[dict]:
        return [_normalize_container(c) for c in runtime.ps()]

    @app.websocket("/ws/live")
    async def live_feed(ws: WebSocket, token: str | None = None) -> None:
        if token != session_token:
            await ws.close(code=4401)
            return
        await ws.accept()
        queue = state.subscribe()
        try:
            while True:
                event = await queue.get()
                await ws.send_json(event)
        except WebSocketDisconnect:
            pass
        finally:
            state.unsubscribe(queue)

    if DASHBOARD_DIST.is_dir():
        # Mounted last so it never shadows the /api/* and /ws/live routes
        # above -- Starlette matches routes in registration order.
        app.mount("/", StaticFiles(directory=str(DASHBOARD_DIST), html=True), name="dashboard")
    else:
        logger.info("dashboard/dist not built (run `npm run build` in /dashboard) — serving API only on this port")

    return app
