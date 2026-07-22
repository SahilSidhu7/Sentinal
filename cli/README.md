# /cli — Sentinal (Team B)

Branch: `cli` · Spec: `docs/SPEC.md` §3 (Modules 3, 7), §6.4-6.5 (see prior spec rev), §8

Owns: **live monitoring** — the agent that builds/launches and watches the monitored container. Everything in this doc runs as a `sentinal` command — there is no step in the normal workflow where you're expected to hand-run `docker build`, `docker run`, or a standalone script.

## Scope

- Target registration with core backend (`/agent/register`, per-deployment token) — degrades to a local-only registration if core isn't reachable.
- **Builds the container itself** (`sentinal run --path ...`): uses your Dockerfile if you have one, otherwise detects a Python (`requirements.txt`) or Node (`package.json`) app and generates one — you never write or run a Dockerfile/`docker build` by hand. Still supports `--image` for an already-built image (e.g. from a registry).
- Blocks container startup on a local vulnerability scan (secrets/CVE/docker-misconfig/weak-creds — see `docs/VULNERABILITY_CHECKLIST.md`) before traffic hits it.
- Streams the container's stdout/stderr logs → feeds `/model`'s `LogPipeline` directly (same process, no HTTP boundary — see `/model/README.md`). Seeds detection from a pretrained baseline or auto-trains on the target's own first log lines — no separate manual training step. Keeps improving via periodic retraining on the target's own accumulated normal traffic.
- File Integrity Monitor (FIM): `watchdog` baseline hashing + critical-file change flags over any bind-mounted volume.
- Ships structured findings/attack events to core backend (`POST /agent/events/batch`, best-effort — skipped if core isn't running) — raw logs never leave this process.
- Serves `/dashboard`'s local status API + built UI together on one port (`GET /api/score|findings|attacks|containers|settings`, `WS /ws/live`) — spec §8: "`/dashboard` — served by `/cli`, for single-box operators without the full `/backend` running."
- Exposes the local ban-action API (`POST /agent/actions/ban {ip, ttl}`): when core flags an attacker IP, it calls this endpoint and the CLI drops it inside the container's own network namespace (`iptables` via `docker exec`), TTL-based and auto-reversed. Never core-initiated host-wide.
- **Tracks each target's running container internally** (persisted in `~/.sentinal/<target_id>.json`) — `stop`/`logs`/`serve-ban-api` all resolve the container from `--target-id` alone; you never need to look up or paste a raw docker container ID.

## Stack

Python (Typer), `docker` CLI for image builds + container lifecycle, `watchdog` for FIM, FastAPI/uvicorn for the local ban API + dashboard status API.

## Setup

```bash
cd cli
pip install -r requirements.txt   # installs /model + /backend editable too (-e ../model, -e ../backend)
```

(Repo-root `scripts/install.sh` does this plus the ONNX export and dashboard build in one shot — see the root README.)

## Workflow

```bash
sentinal register --target-id my-app --backend-url http://localhost:8000
sentinal run --target-id my-app --path ./my-app --port 8080:8080
```

Open `http://localhost:8765` — the dashboard UI + JSON API are both served there by this same process.

```bash
sentinal logs --target-id my-app        # tail its output — no container ID needed
sentinal stop --target-id my-app        # stop it — no container ID needed
```

## Commands

### `register --target-id ID --backend-url URL`
Registers the target with core, persists `~/.sentinal/<target_id>.json` (backend URL, deployment token, and later the running container id). If core is unreachable, registers locally anyway with no token — every core-facing feature elsewhere in this CLI is already best-effort, so a target still fully works standalone.

### `run --target-id ID (--path DIR | --image IMAGE) [options]`
The main loop. Exactly one of `--path`/`--image` is required.

| Option | Default | What it does |
|---|---|---|
| `--path DIR` | — | Build from source. Uses `DIR/Dockerfile` if present; otherwise detects Python (`requirements.txt` + `app.py`/`main.py`/`wsgi.py`/`manage.py`) or Node (`package.json`'s `"start"` script, or `index.js`/`server.js`/`app.js`) and generates a Dockerfile (never written into your source tree). Built image is tagged `sentinal/<target_id>:latest`. |
| `--image IMAGE` | — | Run an already-built image instead (e.g. one you pulled from a registry). |
| `--name NAME` | container-generated | Container name. |
| `--port HOST:CONTAINER` | none | Port mapping; repeatable. |
| `--env KEY=VALUE` | none | Env var; repeatable. |
| `--volume HOST:CONTAINER` | none (or auto-added — see below) | Bind mount; repeatable. |
| `--ban-api-port` | 8787 | Local port for the ban-action API. |
| `--status-api-port` | 8765 | Local port serving the dashboard UI + JSON API together. |
| `--force` | off | Start even if the startup scan finds a `critical` finding. |
| `--batch-size` | 50 | Log lines per `detect()` batch. |
| `--baseline-lines` | 200 | Lines to auto-train a fresh target's baseline on, if not seeding. |
| `--seed-model` | `nginx` | Pretrained dataset baseline to seed detection from (`nginx`/`loghub-apache`/`loghub-linux`/`loghub-ssh`/`csic2010`, see `model/README.md`'s eval table) — `none` to cold-start on the target's own traffic instead (do this when your log format doesn't resemble any shipped dataset). |
| `--retrain-every` | 500 | Retrain the baseline after this many freshly observed normal-traffic lines (continuous improvement) — `0` disables. |

If `--path` is given and you didn't pass your own `--volume`, the source directory is auto-mounted read-accessible at `/app_source` so the startup scanner can see it (secrets/dependency files) even when your Dockerfile's own `COPY` step already baked the source into the image.

Runs the startup scan, aborts on a `critical` finding unless `--force`, then streams logs into detection for the container's lifetime. Persists the running container's id into the target's config as it starts, and clears it on clean shutdown — that's what makes `stop`/`logs`/`serve-ban-api --target-id` work without a raw docker ID.

### `scan --target-id ID [--volume HOST:CONTAINER ...]`
Runs the startup vulnerability scan standalone — no container needs to be running. Useful to check a source tree before deploying it.

### `stop --target-id ID`
Stops the target's tracked container. Errors clearly if nothing is tracked (nothing running, or `run` already exited cleanly).

### `logs --target-id ID [--follow / --no-follow]`
Tails the target's tracked container's output (full history + follow by default; `--no-follow` prints what's there and exits).

### `serve-ban-api (--target-id ID | --container-id ID) [--host] [--port]`
Runs the ban-action API standalone against a container — normally started for you inside `run`; use this to restart it separately without restarting the whole monitoring loop. Prefer `--target-id`; `--container-id` is there for a container `run` isn't tracking (started outside sentinal).

### `fim-baseline --root PATH --target-id ID`
(Re)builds the file-integrity baseline hash set for a path, independent of `run`.

### `status --target-id ID`
Prints the target's full persisted config as JSON — backend URL, token (redact before sharing), watch paths, and the tracked container id if one is running.

### `upgrade [--skip-dashboard-build]`
Pulls the latest code (`git pull` — must be a git checkout) and reinstalls `/model` + `/backend` + `/cli` editable, then rebuilds `/dashboard`'s static assets. Equivalent to `scripts/upgrade.sh`, for when `sentinal` is already on `PATH` and the venv is active.

### `help` / `--help` / `--version`
`help` and `--help` show the same thing; `--version` prints the installed version.

## Contract you depend on

```python
from vibesentinel_model.pipeline import LogPipeline
from vibesentinel_model import EscalationTracker, extract_source_ip
from vibesentinel_scanner import Scanner
```

See `/model/README.md` for `train()`/`detect()` signatures and `docs/VULNERABILITY_CHECKLIST.md` for what the scanner checks. `sentinal.pipeline.get_pipeline()`/`get_escalation_tracker()` and `sentinal.scanner.run_startup_scan()` all return `None` and degrade gracefully if the corresponding package isn't installed. Also depends on `/backend`'s `POST /agent/events/batch`/`/agent/register` (spec §6, best-effort — startup scanning and detection both work with no core backend running at all).

## Known platform limitation

FIM (`watchdog`) and the source-scan volume path both split `--volume HOST:CONTAINER` on `:` to get the host side. That's correct for Linux host paths (this project's actual target — self-hosted Linux servers, per `docs/SPEC.md` §1) but breaks on a Windows-style host path (`C:\...` has its own colon). If you're developing on Windows, either skip `--volume`/`--path`'s auto-mount or pass a Git-Bash-style path from a shell where docker resolves it correctly — this is a dev-machine-only wrinkle, not something the product needs to handle for its actual deployment target.
