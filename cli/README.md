# /cli — Sentinel-Agent CLI (Team B)

Branch: `cli` · Spec: `docs/SPEC.md` §3 (Modules 3, 7), §6.4-6.5 (see prior spec rev), §8

Owns: **live monitoring** — the agent that runs on the monitored host/container.

## Scope
- Target registration with core backend (`/agent/register`, per-deployment token).
- Log tailing (nginx/apache/syslog/app logs) -> feeds `/model`'s `LogPipeline` directly (same process, no HTTP boundary — see `/model/README.md`).
- File Integrity Monitor (FIM): `watchdog` baseline hashing + critical-file change flags.
- Ships structured findings/attack events to core backend (`POST /agent/events/batch`) — raw logs never leave this process.
- Exposes the local ban-action API (`POST /agent/actions/ban {ip, ttl}`), scoped to this agent's own network namespace. Never core-initiated host-wide.

## Stack
Python (Typer or Click).

## Contract you depend on
```python
from vibesentinel_model.pipeline import LogPipeline
```
See `/model/README.md` for `train()`/`detect()` signatures — don't wait on `/model` finishing the ONNX export step to start wiring the CLI skeleton; stub `LogPipeline` calls until artifacts exist.

## Setup (once scaffolded)
```
cd cli
pip install -r requirements.txt
python -m vibesentinel_cli --help
```
