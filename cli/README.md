# /cli — Sentinal (Team B)

Branch: `cli` · Spec: `docs/SPEC.md` §3 (Modules 3, 7), §6.4-6.5 (see prior spec rev), §8

Owns: **live monitoring** — the agent that launches and watches the monitored container.

## Scope
- Target registration with core backend (`/agent/register`, per-deployment token).
- Launches and owns the monitored container (`docker run`), blocking startup on a local startup vulnerability scan (secrets/CVE/docker-misconfig/weak-creds — see `docs/VULNERABILITY_CHECKLIST.md`) before traffic hits it.
- Streams the container's stdout/stderr logs -> feeds `/model`'s `LogPipeline` directly (same process, no HTTP boundary — see `/model/README.md`). Auto-trains a fresh target's anomaly baseline on its first `baseline_lines` of traffic — no separate manual training step needed.
- File Integrity Monitor (FIM): `watchdog` baseline hashing + critical-file change flags over any bind-mounted volume.
- Ships structured findings/attack events to core backend (`POST /agent/events/batch`, best-effort — skipped if core isn't running) — raw logs never leave this process.
- Serves `/dashboard`'s local status API (`GET /api/score|findings|attacks|containers|settings`, `WS /ws/live`) directly off this process's in-memory state — spec §8: "`/dashboard` — served by `/cli`, for single-box operators without the full `/backend` running."
- Exposes the local ban-action API (`POST /agent/actions/ban {ip, ttl}`): when core flags an attacker IP, it calls this endpoint and the CLI drops it inside the container's own network namespace (`iptables` via `docker exec`), TTL-based and auto-reversed. Never core-initiated host-wide.

## Stack
Python (Typer), `docker` CLI for container lifecycle, `watchdog` for FIM, FastAPI/uvicorn for the local ban API + dashboard status API.

## Contract you depend on
```python
from vibesentinel_model.pipeline import LogPipeline
from vibesentinel_model import EscalationTracker, extract_source_ip
from vibesentinel_scanner import Scanner
```
See `/model/README.md` for `train()`/`detect()` signatures and `docs/VULNERABILITY_CHECKLIST.md` for what the scanner checks. `sentinal.pipeline.get_pipeline()` / `get_escalation_tracker()` and `sentinal.scanner.run_startup_scan()` all return `None` and degrade gracefully if the corresponding package isn't installed.

`run`'s log loop auto-trains a baseline from the target's first `baseline_lines` (default 200) lines, then ships `log_anomaly` events per flagged line plus an `attack_event` whenever `EscalationTracker` sees enough sustained hits from one source IP (per-line noise is never enough on its own — see `/model/README.md`'s false-positive numbers). Every finding/attack also lands in the in-process `AgentState` (`sentinal/state.py`) that the dashboard status API reads.

Also depends on `/backend`'s `POST /agent/events/batch` / `/agent/register` (spec §6, best-effort — startup scanning and detection both work with no core backend running at all).

## Setup (once scaffolded)
```
cd cli
pip install -r requirements.txt   # installs /model + /backend editable too (-e ../model, -e ../backend)
sentinal register --target-id my-app --backend-url http://localhost:8000
sentinal run --target-id my-app --image my-app:latest --port 8080:8080 --volume ./app:/app
```
Then point `/dashboard` (`cd ../dashboard && npm run dev`) at this agent — its Vite dev proxy already defaults to `http://localhost:8765` (`VITE_AGENT_URL` to override), matching `run`'s default `--status-api-port`.

## Commands
- `register` — registers the target, persists backend URL + token to `~/.sentinal/<target_id>.json`.
- `scan` — runs the local startup vulnerability scanner standalone, prints findings (no backend or running container needed).
- `run` — the core loop: local startup scan -> `docker run` the target image -> FIM on any `--volume` mounts -> auto-train + stream logs into `LogPipeline` -> ship anomalies to core (best-effort) and to the local dashboard API -> serve the ban API + dashboard status API for the container's lifetime.
- `fim-baseline` — (re)builds the FIM baseline hash set for a path.
- `serve-ban-api` — runs the ban API standalone against an already-running container id.
- `status` — prints the persisted config for a target.
