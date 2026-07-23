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

Repo-root `scripts/install.sh` is the normal path — one command, works standalone or via `curl | bash` (see the root README) — and finishes by symlinking `sentinal` onto `PATH` (`/usr/local/bin` or `~/.local/bin`) so it behaves like any other globally-installed CLI tool. No `source .venv/bin/activate` in the day-to-day workflow.

Building this package directly instead:

```bash
cd cli
pip install -r requirements.txt   # installs /model + /backend editable too (-e ../model, -e ../backend)
```

## Workflow

The one-command path — from your app's own source directory, in any shell (no venv activation needed once installed):

```bash
sentinal start --port 8080:8080
```

No `register` step, no `--target-id`, no `--path`: `start` (an alias for `run`) defaults `--path` to `.`, picks a session id from the folder name (e.g. `my-app-a1b2`), and auto-registers that session against `--backend-url` (default `http://localhost:8000`) — locally-only if core isn't reachable. It builds/launches the container and runs the startup scan **in this terminal** (so you see build/scan failures immediately), then hands the actual watch loop off to a detached background process and returns control to you:

```
session: my-app-a1b2 (new — registered locally, core unreachable)
...
  dashboard ready -> http://localhost:8765

sentinal is watching 'my-app-a1b2' in the background (pid 48213):
  sentinal logs --target-id my-app-a1b2     tail the container's output
  sentinal scan --target-id my-app-a1b2     re-run the vulnerability scan
  sentinal status --target-id my-app-a1b2   check what's running
  sentinal stop --target-id my-app-a1b2     stop everything
```

```bash
sentinal logs --target-id my-app-a1b2        # tail its output — no container ID needed
sentinal stop --target-id my-app-a1b2        # stops the background watcher + the container
```

Prefer to stay attached instead (e.g. running under systemd, or debugging)? `sentinal start --foreground` skips the background hand-off and blocks in this terminal until Ctrl+C, same as `run` used to.

For a fixed/known name instead of an auto-generated session id, or to pre-register before ever launching a container, use `register` + `run --target-id` explicitly (below).

## Commands

### `register --target-id ID --backend-url URL`
Registers a target with a name you choose, persists `~/.sentinal/<target_id>.json` (backend URL, deployment token, and later the running container id). If core is unreachable, registers locally anyway with no token. `run`/`start` do this automatically with an auto-generated id if you don't call it yourself first — every core-facing feature elsewhere in this CLI is already best-effort, so a target fully works standalone either way.

### `run` / `start --target-id ID (--path DIR | --image IMAGE) [options]`
The main loop. `start` is an alias for `run` for the one-command path. `--target-id` and `--path`/`--image` are all optional: with neither `--path` nor `--image`, `--path` defaults to the current directory; with no `--target-id`, one is generated from the source folder (or image) name and a random suffix, and auto-registered against `--backend-url` if it doesn't already exist.

| Option | Default | What it does |
|---|---|---|
| `--target-id ID` | auto-generated | Session id. Omit it to let `start`/`run` pick one and register it for you. |
| `--path DIR` | `.` if neither `--path` nor `--image` given | Build from source. Uses `DIR/Dockerfile` if present; otherwise detects Python (`requirements.txt` + `app.py`/`main.py`/`wsgi.py`/`manage.py`) or Node (`package.json`'s `"start"` script, or `index.js`/`server.js`/`app.js`) and generates a Dockerfile (never written into your source tree). Built image is tagged `sentinal/<target_id>:latest`. |
| `--image IMAGE` | — | Run an already-built image instead (e.g. one you pulled from a registry). |
| `--backend-url URL` | `http://localhost:8000` | Used only if `--target-id` has no existing config yet, to auto-register it. |
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
| `--foreground` | off | Stay attached and block in this terminal (Ctrl+C to stop) instead of handing the watch loop off to a background process. |
| `--admin-password` | `$SENTINAL_ADMIN_PASSWORD`, else `admin` | Password required to log into the dashboard at `--status-api-port`. Falling back to `admin` prints a warning — set this (or the env var) to anything beyond local testing. |

The dashboard login is a single admin password, checked by `--status-api-port`'s API (`POST /api/auth/login`) against `--admin-password`/`$SENTINAL_ADMIN_PASSWORD` — it's resolved once in `run` and passed down to whichever process ends up serving the dashboard (the background `monitor` process by default, or this one under `--foreground`), which mints one session token for its lifetime. Stopping and re-running the target (or restarting the background monitor) mints a fresh token and logs everyone out. This is the local, single-operator status site's auth (spec §8), not the core backend's (not built yet).

If `--path` is given and you didn't pass your own `--volume`, the source directory is auto-mounted read-accessible at `/app_source` so the startup scanner can see it (secrets/dependency files) even when your Dockerfile's own `COPY` step already baked the source into the image.

Builds, launches the container, and runs the startup scan synchronously in this terminal — aborting on a `critical` finding unless `--force` — so failures are visible immediately. Persists the running container's id into the target's config as it starts (what makes `stop`/`logs`/`serve-ban-api --target-id` work without a raw docker ID). Then, unless `--foreground`, spawns a detached `monitor` process (ban API, dashboard status API, FIM, log-tailing detection loop) and returns; that process's own diagnostics land in `~/.sentinal/<target_id>.log`, and its pid is persisted so `stop`/`status` can find and signal it.

### `scan --target-id ID [--volume HOST:CONTAINER ...]`
Runs the startup vulnerability scan standalone — no container needs to be running. Useful to check a source tree before deploying it, or to re-scan a target that's already running.

### `stop --target-id ID`
Stops the target's background monitor (if `run`/`start` spawned one, via `SIGTERM` — same clean shutdown path as Ctrl+C) and its tracked container. Errors clearly if nothing is tracked.

### `logs --target-id ID [--follow / --no-follow]`
Tails the target's tracked container's output (full history + follow by default; `--no-follow` prints what's there and exits). This is the app's own output — for `sentinal`'s internal diagnostics from a background `run`, see `~/.sentinal/<target_id>.log`.

### `serve-ban-api (--target-id ID | --container-id ID) [--host] [--port]`
Runs the ban-action API standalone against a container — normally started for you inside `run`'s background monitor; use this to restart it separately without restarting the whole monitoring loop. Prefer `--target-id`; `--container-id` is there for a container `run` isn't tracking (started outside sentinal).

### `fim-baseline --root PATH --target-id ID`
(Re)builds the file-integrity baseline hash set for a path, independent of `run`.

### `status --target-id ID`
Prints the target's full persisted config as JSON — backend URL, token (redact before sharing), watch paths, the tracked container id, and the background monitor's pid, if any. Also prints whether that pid is actually still alive.

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

## Docker permissions

`run`/`start` shell out to `docker`, which needs your user in the `docker` group (or root) to reach `/var/run/docker.sock`. If you see `permission denied ... docker.sock`, fix it once — `sudo usermod -aG docker $USER && newgrp docker` (or log out/in) — rather than running `sentinal` itself under `sudo`: `sudo` resets `PATH`, so it won't find a venv-only `sentinal` install. `scripts/install.sh` checks for group membership and warns at install time if it's missing.

## Known platform limitation

FIM (`watchdog`) and the source-scan volume path both split `--volume HOST:CONTAINER` on `:` to get the host side. That's correct for Linux host paths (this project's actual target — self-hosted Linux servers, per `docs/SPEC.md` §1) but breaks on a Windows-style host path (`C:\...` has its own colon). If you're developing on Windows, either skip `--volume`/`--path`'s auto-mount or pass a Git-Bash-style path from a shell where docker resolves it correctly — this is a dev-machine-only wrinkle, not something the product needs to handle for its actual deployment target.
