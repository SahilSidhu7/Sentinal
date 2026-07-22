# /cli — Sentinal (Team B)

Branch: `cli` · Spec: `docs/SPEC.md` §3 (Modules 3, 7), §6.4-6.5 (see prior spec rev), §8

Owns: **live monitoring** — the agent that launches and watches the monitored container.

## Scope
- Target registration with core backend (`/agent/register`, per-deployment token).
- Launches and owns the monitored container (`docker run`), blocking startup on the backend's Scanner (`POST /targets/{id}/scan` — secrets/CVE/leaks) before traffic hits it.
- Streams the container's stdout/stderr logs -> feeds `/model`'s `LogPipeline` directly (same process, no HTTP boundary — see `/model/README.md`).
- File Integrity Monitor (FIM): `watchdog` baseline hashing + critical-file change flags over any bind-mounted volume.
- Ships structured findings/attack events to core backend (`POST /agent/events/batch`) — raw logs never leave this process.
- Exposes the local ban-action API (`POST /agent/actions/ban {ip, ttl}`): when core flags an attacker IP, it calls this endpoint and the CLI drops it inside the container's own network namespace (`iptables` via `docker exec`), TTL-based and auto-reversed. Never core-initiated host-wide.

## Stack
Python (Typer), `docker` CLI for container lifecycle, `watchdog` for FIM, FastAPI/uvicorn for the local ban API.

## Contract you depend on
```python
from vibesentinel_model.pipeline import LogPipeline
```
See `/model/README.md` for `train()`/`detect()` signatures — don't wait on `/model` finishing the ONNX export step to start wiring the CLI skeleton; `sentinal.pipeline.get_pipeline()` returns `None` and degrades to tail-only if artifacts aren't there yet.

Also depends on `/backend`'s `POST /targets/{id}/scan` (startup checks) and `POST /agent/events/batch` / `/agent/register` (spec §6) — stub these against a mock backend until `/backend` ships them.

## Setup (once scaffolded)
```
cd cli
pip install -e .
sentinal register --target-id my-app --backend-url http://localhost:8000
sentinal run --target-id my-app --image my-app:latest --port 8080:8080
```

## Commands
- `register` — registers the target, persists backend URL + token to `~/.sentinal/<target_id>.json`.
- `scan` — triggers the backend startup scan standalone, prints findings.
- `run` — the core loop: startup scan -> `docker run` the target image -> FIM on any `--volume` mounts -> stream logs into `LogPipeline` -> ship anomalies -> serve the local ban API for the container's lifetime.
- `fim-baseline` — (re)builds the FIM baseline hash set for a path.
- `serve-ban-api` — runs the ban API standalone against an already-running container id.
- `status` — prints the persisted config for a target.
