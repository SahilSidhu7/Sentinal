# Sentinal (VibeSentinel)

Local-first security monitoring for self-hosted servers and Docker
containers. Point it at your app's source, and it builds the container,
runs a startup vulnerability scan, watches its logs for attacks with a
local Drain3 + ONNX + Isolation Forest pipeline (**no LLM anywhere in the
detection path**), and shows all of it on a live dashboard — no network
dependency for the core loop, and no manual `docker build`/`docker run`.

**Core loop:** `Watch → Scan → Detect → Show → Act`

New here / wondering if it's for you? Read the [**2-minute pitch**](docs/PITCH.md).

Full design: [`docs/SPEC.md`](docs/SPEC.md). What gets checked at startup:
[`docs/VULNERABILITY_CHECKLIST.md`](docs/VULNERABILITY_CHECKLIST.md). Full
CLI reference: [`cli/README.md`](cli/README.md). Live model numbers:
[`docs/MODEL_STATS.md`](docs/MODEL_STATS.md).

## Hosted management platform (v0.3.0) — new

As of v0.3.0 there are **two ways to run Sentinal**:

1. **CLI agent** (original) — point `sentinal run` at your app; it builds and
   monitors the container itself. Documented below.
2. **Hosted platform** (new) — a management system where each *project* is an
   isolated Linux **environment** you drive through **two browser terminals**:
   one to run your server, one to run tests and watch live alerts. A short
   access id is auto-generated per project. The model taps the server
   terminal's live output in real time; everything else is driven from a
   single dashboard served on one port.

   ```bash
   # Installed the binary? The platform is a subcommand — nothing else to set up:
   sentinal core                              # http://localhost:8000
   # open http://localhost:8000 → create a project → open its two terminals
   ```

   From a source checkout instead of the binary:

   ```bash
   pip install -e "./backend[core]"          # FastAPI core
   cd dashboard && npm ci && npm run build    # build the UI (served by the core)
   sentinal core            # or: sentinal-core   (equivalent standalone launcher)
   ```

   **Behind a domain / reverse proxy.** The UI, API, and websockets are all
   served on one origin, so the dashboard just calls whatever host you load it
   from — no endpoint config. Your proxy must forward WebSocket upgrades for the
   terminals/alerts to work, e.g. nginx:

   ```nginx
   location / {
       proxy_pass http://127.0.0.1:8000;
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection "upgrade";
       proxy_set_header Host $host;
   }
   ```

   **Login.** The dashboard is gated by an admin password — **`admin`** by
   default. Change it before exposing the platform on the network:
   `sentinal core --host 0.0.0.0 --admin-password 'something-strong'` (or set
   `$SENTINAL_ADMIN_PASSWORD`). The password mints a per-process session token
   that guards every API call and both terminal/alert websockets — so an open
   `0.0.0.0` port isn't a free shell into your environments.

   **Demo project**: click **Load demo project** on the Overview — it spins up a
   project preloaded with a demo server + attack-traffic generator (not baked
   into normal environments). In the *server* terminal run
   `python3 /opt/demo_server.py`, in the *tests* terminal run
   `python3 /opt/traffic.py`, and watch the alert feed. Measured 100% attack
   recall / 0 false positives on a 40-request run — see
   [`docs/MODEL_STATS.md`](docs/MODEL_STATS.md).

   **Does it auto-run on install?** No — the installer sets up the `sentinal`
   binary; the hosted platform starts on demand with `sentinal core` (a security
   tool shouldn't open a listening server without you asking). To keep it
   running / auto-start on boot, put it under a process manager, e.g. systemd:

   ```ini
   # /etc/systemd/system/sentinal-core.service
   [Service]
   ExecStart=/usr/local/bin/sentinal core --host 0.0.0.0 --port 8000
   Restart=always
   User=youruser
   [Install]
   WantedBy=multi-user.target
   ```
   then `sudo systemctl enable --now sentinal-core`.

## What's real today

| Piece | Status |
|---|---|
| `/model` — Drain3 + ONNX MiniLM + Isolation Forest, 5 pretrained dataset baselines shipped | Working, tested (see `model/README.md`) |
| `/backend`'s `vibesentinel_scanner` — startup vuln scan (secrets/CVE/docker-misconfig/weak-creds) | Working, tested |
| `/cli` (`sentinal`) — registers targets, **builds + launches + monitors containers itself**, runs the scan, feeds logs into `/model`, serves the local ban API | Working, tested |
| `/dashboard` — one port (JSON API + built UI), admin-password login, in-app Documentation page, plus the new hosted Overview/Environments pages | Working, tested |
| `/backend`'s `vibesentinel_core` — hosted platform: per-project Linux environments, two browser terminals (PTY over WebSocket), live model monitoring, project persistence, single-port dashboard | **New in v0.3.0**, verified end-to-end (create → id → 2 terminals → live attack alert) |
| Core `/backend` multi-target aggregation, auth, SQLite audit log | Partial — `vibesentinel_core` covers project/env management + live monitoring; JWT auth + SQLite history not yet wired. Standalone-per-target still works with no core. |

The marketing/landing site lives in its own repo now:
[sentinal-landing](https://github.com/SahilSidhu7/sentinal-landing)
(hosted at [sahilsidhu7.github.io/sentinal-landing](https://sahilsidhu7.github.io/sentinal-landing/)) — it isn't part of the monitoring loop and doesn't need to ship alongside this code.

## Install

One line, on any Linux server (Linux-only; on Windows use WSL):

```bash
curl -fsSL https://sahilsidhu7.github.io/sentinal-landing/install.sh | bash
```

(Or straight from this repo, no landing site involved:
`curl -fsSL https://raw.githubusercontent.com/SahilSidhu7/Sentinal/main/scripts/install.sh | bash`
— both run the same `scripts/install.sh`.)

This downloads the **self-contained `sentinal` binary** for your architecture
(x86_64 or aarch64) from the latest [GitHub Release](https://github.com/SahilSidhu7/Sentinal/releases)
and drops it on your `PATH` (`/usr/local/bin`, or `~/.local/bin` if that's not
writable). No repo clone, no Python, no virtualenv — the binary bundles its own
Python runtime, the ONNX embedding model, the anomaly models, and the dashboard
UI. It also checks Docker is present and that you're in the `docker` group, so
`sentinal run`/`start` won't hit a permission error later.

```bash
sentinal --version
sentinal --help
```

### Other ways to install

```bash
# Debian/Ubuntu package (needs sudo)
SENTINAL_INSTALL_METHOD=deb curl -fsSL https://raw.githubusercontent.com/SahilSidhu7/Sentinal/main/scripts/install.sh | bash

# pin a specific version
SENTINAL_VERSION=0.1.0 curl -fsSL .../install.sh | bash

# or grab an asset from a release by hand
curl -fL -o sentinal https://github.com/SahilSidhu7/Sentinal/releases/latest/download/sentinal-linux-x86_64
chmod +x sentinal && sudo mv sentinal /usr/local/bin/
# ...or:  sudo dpkg -i sentinal_<version>_amd64.deb
```

The installer isn't code-signed; on a first run some hardened setups may warn —
it's a plain ELF binary you can inspect. One-time step.

**Building from source / contributing?** See [`cli/README.md`](cli/README.md)
"Develop from source" for the editable-install dev workflow, and
[`packaging/`](packaging/) for how the release binary is built.

**After install, every feature is a `sentinal` command** — building images,
running/stopping containers, tailing logs, scanning, upgrading. There is no
second script or manual docker step in the normal workflow.

## Quick start

From your app's own source directory:

```bash
sentinal start --port 8080:8080
```

No `register`, no `--target-id`, no `--path`, no `--image`, no Dockerfile
required from you. `sentinal start` (an alias for `run`):

1. Picks a session id from the folder name (e.g. `my-app-a1b2`) and
   auto-registers it — locally-only if core isn't reachable.
2. **Builds the container itself.** Uses `./Dockerfile` if you have one;
   otherwise detects your app's stack (`requirements.txt` → Python,
   `package.json` → Node) and generates a Dockerfile — you never write or
   run `docker build` yourself. (`--image some:tag` still works if you'd
   rather run something already built.)
3. Launches the container.
4. Runs the startup vulnerability scan (`docs/VULNERABILITY_CHECKLIST.md`)
   and refuses to start on a `critical` finding (`--force` to override) —
   all of this happens in your terminal, so failures are visible
   immediately.
5. **Hands off to a background process** for the rest of the target's
   lifetime, and returns you to the shell:
   - Seeds anomaly detection from a pretrained baseline (`--seed-model`,
     default `nginx`) or cold-starts on this target's own first 200 log
     lines (`--seed-model none`) — see "Self-improving detection" below.
   - Streams logs into the anomaly pipeline, escalating sustained per-IP
     attack patterns.
   - Serves **the dashboard UI and its JSON API together** on one port
     (`--status-api-port`, default **8765**) — open
     `http://<this-host>:8765` in a browser, gated behind a single
     admin-password login (`--admin-password`/`$SENTINAL_ADMIN_PASSWORD`,
     defaults to `admin` with a printed warning) — see `cli/README.md`'s
     `run` options table.
   - Serves the local ban-action API (`--ban-api-port`, default 8787) for
     IP-ban coordination.
6. **Tracks the running container and background process against its
   session id** — no docker container ID or PID to find or paste anywhere:

```bash
sentinal logs --target-id my-app-a1b2     # tail its output
sentinal stop --target-id my-app-a1b2     # stop the background watcher + the container
sentinal status --target-id my-app-a1b2   # see everything sentinal knows about it, incl. whether it's running
```

Want to stay attached in the terminal instead (e.g. under systemd)?
`sentinal start --foreground` skips the background hand-off.

Want to see this whole loop working against a real (deliberately
vulnerable) target first? See
[`../sentinel-demo-app`](https://github.com/SahilSidhu7/sentinel-demo-app) —
a small Flask app + attack-traffic generator built specifically to showcase
every piece of this pipeline end to end:

```bash
git clone https://github.com/SahilSidhu7/sentinel-demo-app.git
sentinal start --target-id demo --path ./sentinel-demo-app --port 5000:5000 --seed-model none --force
```

## Self-improving detection

A target doesn't stay pinned to whatever it started with:

- **Seeding**: new targets can start from one of 5 pretrained dataset models
  shipped in `model/artifacts/` (`nginx`, `loghub-apache`, `loghub-linux`,
  `loghub-ssh`, `csic2010`) — real detection from the first batch instead of
  waiting to accumulate a baseline. Pick the one closest to your log format,
  or `--seed-model none` to cold-start on the target's own traffic instead
  (better when your log format doesn't resemble any shipped dataset).
- **Continuous retraining**: `/cli` accumulates each target's own
  normal-flagged traffic and periodically retrains on it
  (`--retrain-every`, default every 500 lines, capped to a 3000-line rolling
  window) — detection keeps adapting to what *this* target's real traffic
  looks like, on top of whatever it was seeded with.

See `model/README.md`'s "Continuous improvement" section for the reasoning
and false-positive tradeoffs.

## CLI command reference

Run `sentinal help` (or `--help`) any time for the live version of this.
Every one of these is a `sentinal <command>` — nothing here is a separate
script you run by hand.

| Command | Required | Key options | What it does |
|---|---|---|---|
| `register` | `--target-id`, `--backend-url` | — | Registers a target, persists its config (backend URL, token, later its container id and background pid) to `~/.sentinal/<target_id>.json`. Degrades to a tokenless local registration if core is unreachable. `run`/`start` do this automatically if you skip it. |
| `scan` | `--target-id` | `--volume` (repeatable) | Runs the startup vulnerability scan standalone — no container needs to be running. Good for checking source before deploying it, or re-scanning one that's already up. |
| `run` / `start` | none — all optional | `--target-id`; one of `--path`/`--image` (defaults `--path` to `.`); `--port`, `--env`, `--volume` (all repeatable); `--name`; `--force`; `--foreground`; `--ban-api-port` (8787); `--status-api-port` (8765); `--batch-size` (50); `--baseline-lines` (200); `--seed-model` (`nginx`); `--retrain-every` (500); `--admin-password` (`$SENTINAL_ADMIN_PASSWORD`, else `admin`) | Builds (if `--path`) and launches the container, runs the startup scan synchronously, then hands the watch loop off to a background process and returns — see "Quick start" above. `start` is an alias for `run`. Full option table in `cli/README.md`. |
| `stop` | `--target-id` | — | Stops the target's background monitor (if any) and its tracked container. |
| `logs` | `--target-id` | `--follow`/`--no-follow` (default follow) | Tails the target's tracked container's output. |
| `status` | `--target-id` | — | Prints the target's full persisted config as JSON (container id, background pid) and whether that pid is actually still running. |
| `fim-baseline` | `--root`, `--target-id` | — | (Re)builds the file-integrity baseline hash set for a path, independent of `run`. |
| `serve-ban-api` | one of `--target-id`/`--container-id` | `--host`, `--port` (8787) | Runs the ban-action API standalone — normally started for you inside `run`'s background monitor. |
| `upgrade` | — | — | Installed binary: re-runs the installer to fetch and replace itself with the latest release. Source checkout (dev): `git pull` + editable reinstall (`--skip-dashboard-build` available there). |
| `help` | — | — | Same as `--help`. |
| `--version` | — | — | Prints the installed version. |

## Upgrading

```bash
sentinal upgrade
```

That re-runs the installer, which downloads the newest release binary and
replaces the one on your `PATH`. Re-running the one-line install command does
exactly the same thing (the installer is idempotent):

```bash
curl -fsSL https://raw.githubusercontent.com/SahilSidhu7/Sentinal/main/scripts/install.sh | bash
```

(Working from a source checkout instead? `sentinal upgrade` there does a
`git pull` + editable reinstall — see [`cli/README.md`](cli/README.md).)

## Architecture

```
Watch  → docker build/run (sentinal run --path, auto-Dockerfile or your own)
Scan   → backend/vibesentinel_scanner: secrets, docker misconfig,
         dependency CVEs, weak credentials — before traffic ever hits it
Detect → model/vibesentinel_model: Drain3 templates → ONNX MiniLM
         embeddings → per-target Isolation Forest, seeded from a
         pretrained baseline or cold-started, retrained continuously
Show   → cli/sentinal/local_api.py: dashboard UI + JSON API on one port,
         backed by an in-process AgentState (no core backend required)
Act    → escalation ladder (log_only → flag_for_review →
         rate_limit_and_challenge → ban_ip, always manual-confirm by
         default) → the local ban API, scoped to the container's own
         network namespace, never core-initiated host-wide
```

Every finding/attack event shares one JSON shape end to end — scanner
findings and log-anomaly/attack events both look the same to `/dashboard`,
whether or not a core backend is aggregating them.

## Project layout

```
/cli        sentinal — the agent CLI: registration, image build + container
            lifecycle, log tailing, startup scan, ban API, dashboard status API
/model      Drain3 + ONNX embedding + Isolation Forest — vibesentinel_model
/backend    vibesentinel_scanner (startup vuln checks) + vibesentinel_core
            (hosted platform: environments, browser terminals, live monitoring)
/dashboard  Thin status site, served by /cli (React + Vite + Tailwind)
/docs       Spec + the vulnerability checklist
/scripts    install.sh / upgrade.sh — the one-line installer (downloads the
            release binary) and its update wrapper
/packaging  PyInstaller spec + build scripts that produce the release binary
            and .deb (run on Linux CI — see .github/workflows/release.yml)
```

Marketing site: separate repo, [sentinal-landing](https://github.com/SahilSidhu7/sentinal-landing) (also hosts the one-line installer above).

Each folder's README has its team's scope and the cross-folder contracts it
depends on — see `docs/SPEC.md` §11.1 / `TEAM.md`.

## Known limitations

- **Hosted core is partial** — `vibesentinel_core` handles project/env
  management, browser terminals, live monitoring, and project persistence,
  but JWT auth (the dashboard login is still client-side only) and
  SQLite-backed history/audit across restarts aren't wired yet. The CLI
  agent path works fully standalone against one target regardless.
- **Hosted terminals need a working Docker `exec`** — each environment is a
  container the two terminals `docker exec` into. A wedged Docker daemon
  (where `docker ps` shows a container that `docker exec`/`inspect` can't
  find) blocks the terminals; restart Docker Desktop (`wsl --shutdown`) if so.
- **Windows dev machines**: `--volume`/`--path`'s FIM watcher and
  auto-mount split a host path on `:` to separate host/container sides —
  correct for Linux host paths (this project's actual deployment target)
  but breaks on `C:\...`-style paths, which have their own colon. Not
  fixed, since the product doesn't target Windows hosts — see
  `cli/README.md`'s "Known platform limitation".
- **Dependency-CVE checks need outbound network access** (OSV.dev) — they
  degrade to "not checked this run" rather than failing the scan when
  offline, per the checklist doc.
