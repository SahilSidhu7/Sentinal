"""Thin localhost status API — what /dashboard's src/lib/api.js fetches
against (spec §8: "/dashboard — served by /cli"). Separate from ban_api.py
on purpose: that one is a narrow action endpoint core calls into; this one
is a read/status surface for a human looking at the local dashboard.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from sentinal.container import ContainerRuntime
from sentinal.state import AgentState

logger = logging.getLogger(__name__)


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
    notify_critical_alerts: bool | None = None
    notify_log_summaries: bool | None = None


def create_app(state: AgentState, runtime: ContainerRuntime | None = None) -> FastAPI:
    app = FastAPI(title="sentinal local status API")
    runtime = runtime or ContainerRuntime()

    @app.on_event("startup")
    async def _bind_loop() -> None:
        state.set_event_loop(asyncio.get_running_loop())

    @app.get("/api/score")
    def get_score() -> dict:
        return state.score()

    @app.get("/api/findings")
    def get_findings() -> list[dict]:
        return state.findings

    @app.get("/api/attacks")
    def get_attacks() -> list[dict]:
        return state.attacks

    @app.post("/api/attacks/{attack_id}/{action}")
    def respond_to_attack(attack_id: str, action: str) -> dict:
        ok = state.resolve_attack(attack_id, action)
        return {"ok": ok}

    @app.get("/api/settings")
    def get_settings() -> dict:
        return state.settings

    @app.post("/api/settings")
    def save_settings(update: SettingsUpdate) -> dict:
        state.settings.update({k: v for k, v in update.model_dump().items() if v is not None})
        return state.settings

    @app.get("/api/containers")
    def get_containers() -> list[dict]:
        return [_normalize_container(c) for c in runtime.ps()]

    @app.websocket("/ws/live")
    async def live_feed(ws: WebSocket) -> None:
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

    return app
