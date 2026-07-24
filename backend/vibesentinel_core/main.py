"""FastAPI core for the hosted management platform.

Vertical slice: create a project (-> isolated Linux env + auto id), open its two
browser terminals over websockets, and stream live monitoring alerts the model
raises from the *server* terminal's output.

    POST   /api/projects                      {name?} -> {id, name, running}
    GET    /api/projects                      list
    DELETE /api/projects/{id}                 tear down the environment
    WS     /api/projects/{id}/terminal/{which}  which in {server, tests}
    WS     /api/projects/{id}/alerts          live model alert feed (JSON)
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from vibesentinel_core import _resources
from vibesentinel_core.environment import EnvironmentError, EnvironmentManager
from vibesentinel_core.ids import new_id, slugify
from vibesentinel_core.monitor import LiveMonitor

# Where the project list is persisted so environments survive a backend restart
# (the Docker containers themselves already outlive the process).
STATE_FILE = Path.home() / ".sentinal" / "core_projects.json"
# Built dashboard, if present — lets one port serve UI + API together. Resolved
# through _resources so it works from a source checkout and a frozen binary.
_DASHBOARD_DIST = _resources.dashboard_dist()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("vibesentinel_core")

app = FastAPI(title="VibeSentinel Core")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev: Vite dev server; tighten before any non-local deploy
    allow_methods=["*"],
    allow_headers=["*"],
)

_envs = EnvironmentManager()


class Project:
    def __init__(self, project_id: str, name: str, is_demo: bool = False):
        self.id = project_id
        self.name = name
        self.is_demo = is_demo
        self.monitor = LiveMonitor(project_id)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "running": _envs.is_running(self.id),
            "monitoring": self.monitor.enabled,
            "alert_count": self.monitor.alert_count,
            "is_demo": self.is_demo,
        }


_projects: dict[str, Project] = {}


def _save_projects() -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = [{"id": p.id, "name": p.name, "demo": p.is_demo} for p in _projects.values()]
    STATE_FILE.write_text(json.dumps(data, indent=2))


@app.on_event("startup")
def _restore_projects() -> None:
    """Re-adopt persisted projects on boot. A still-running container is picked
    back up as-is (the user's server keeps running); a missing one is recreated
    so the environment is usable again. Either way its monitor re-seeds."""
    if not STATE_FILE.exists():
        return
    try:
        saved = json.loads(STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        logger.warning("could not read %s — starting with no projects", STATE_FILE)
        return
    for entry in saved:
        pid = entry["id"]
        is_demo = entry.get("demo", False)
        try:
            _envs.ensure_image()
            _envs.create(pid)  # idempotent: reuses a live container, recreates a gone one
            if is_demo:
                _envs.seed_demo(pid)  # re-copy demo assets in case the container was recreated
        except EnvironmentError:
            logger.exception("could not restore environment for %s", pid)
            continue
        _projects[pid] = Project(pid, entry.get("name", pid), is_demo=is_demo)
        logger.info("restored project id=%s", pid)


class CreateProject(BaseModel):
    name: str | None = None
    demo: bool = False  # seed this one project with the demo server + traffic generator


@app.post("/api/projects")
def create_project(body: CreateProject) -> dict:
    default_name = "demo" if body.demo else None
    name = body.name or default_name
    project_id = slugify(name) if name else new_id()
    if project_id in _projects:
        # name collision — fall back to a generated id so the user still gets one
        project_id = new_id()
    try:
        _envs.ensure_image()
        _envs.create(project_id)
        if body.demo:
            _envs.seed_demo(project_id)
    except EnvironmentError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    project = Project(project_id, name or project_id)
    project.is_demo = body.demo
    _projects[project_id] = project
    _save_projects()
    logger.info("project created id=%s name=%r demo=%s", project_id, project.name, body.demo)
    return project.as_dict()


@app.get("/api/projects")
def list_projects() -> list[dict]:
    return [p.as_dict() for p in _projects.values()]


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str) -> dict:
    project = _projects.pop(project_id, None)
    if project is None:
        raise HTTPException(status_code=404, detail="unknown project")
    _envs.destroy(project_id)
    _save_projects()
    return {"deleted": project_id}


def _require(project_id: str) -> Project:
    project = _projects.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="unknown project")
    return project


@app.websocket("/api/projects/{project_id}/terminal/{which}")
async def terminal(ws: WebSocket, project_id: str, which: str) -> None:
    await ws.accept()
    project = _projects.get(project_id)
    if project is None or which not in ("server", "tests"):
        await ws.close(code=1008)
        return
    try:
        proc = await _envs.open_terminal(project_id)
    except Exception:
        logger.exception("failed to open terminal for %s", project_id)
        await ws.close(code=1011)
        return

    tee = project.monitor if which == "server" else None

    async def pump_out() -> None:
        assert proc.stdout is not None
        while True:
            chunk = await proc.stdout.read(65536)
            if not chunk:
                break
            await ws.send_bytes(chunk)
            if tee is not None:
                await tee.feed_bytes(chunk)

    async def pump_in() -> None:
        assert proc.stdin is not None
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            data = msg.get("bytes")
            if data is None and msg.get("text") is not None:
                data = msg["text"].encode("utf-8")
            if data:
                proc.stdin.write(data)
                await proc.stdin.drain()

    out_task = asyncio.create_task(pump_out())
    in_task = asyncio.create_task(pump_in())
    try:
        await asyncio.wait({out_task, in_task}, return_when=asyncio.FIRST_COMPLETED)
    except WebSocketDisconnect:
        pass
    finally:
        for t in (out_task, in_task):
            t.cancel()
        try:
            proc.kill()
        except ProcessLookupError:
            pass


@app.websocket("/api/projects/{project_id}/alerts")
async def alerts(ws: WebSocket, project_id: str) -> None:
    await ws.accept()
    project = _projects.get(project_id)
    if project is None:
        await ws.close(code=1008)
        return
    queue = project.monitor.subscribe()
    await ws.send_json({"type": "status", "monitoring": project.monitor.enabled})
    for past in project.monitor.recent():  # replay history so the feed isn't empty on reconnect
        await ws.send_json(past)
    try:
        while True:
            alert = await queue.get()
            await ws.send_json(alert)
    except WebSocketDisconnect:
        pass
    finally:
        project.monitor.unsubscribe(queue)


# --- static dashboard (single-port UI + API) -----------------------------
# Mounted last so it never shadows the /api routes above. If the dashboard
# hasn't been built (`npm run build` -> dashboard/dist), the API still serves;
# in dev you'd run Vite separately and hit the API cross-origin (CORS is open).
if (_DASHBOARD_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_DASHBOARD_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        # Client-side routes (/environments, /activity, …) all resolve to the
        # SPA entrypoint; real files (favicon, etc.) are served directly.
        candidate = _DASHBOARD_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DASHBOARD_DIST / "index.html")

    logger.info("serving dashboard from %s", _DASHBOARD_DIST)
else:
    logger.info("no built dashboard at %s — API only (run `npm run build` in /dashboard)", _DASHBOARD_DIST)
