# Sentinal (VibeSentinel)

Local-first security monitoring for self-hosted servers and Docker
containers. Point it at your app's source, and it builds the container,
runs a startup vulnerability scan, watches its logs for attacks with a
local Drain3 + ONNX + Isolation Forest pipeline (**no LLM anywhere in the
detection path**), and shows all of it on a live dashboard — no network
dependency for the core loop, and no manual `docker build`/`docker run`.

**Core loop:** `Watch → Scan → Detect → Show → Act`

Full design: [`docs/SPEC.md`](docs/SPEC.md). What gets checked at startup:
[`docs/VULNERABILITY_CHECKLIST.md`](docs/VULNERABILITY_CHECKLIST.md). Full
CLI reference: [`cli/README.md`](cli/README.md).

## What's real today

| Piece | Status |
|---|---|
| `/model` — Drain3 + ONNX MiniLM + Isolation Forest, 5 pretrained dataset baselines shipped | Working, tested (see `model/README.md`) |
| `/backend`'s `vibesentinel_scanner` — startup vuln scan (secrets/CVE/docker-misconfig/weak-creds) | Working, tested |
| `/cli` (`sentinal`) — registers targets, **builds + launches + monitors containers itself**, runs the scan, feeds logs into `/model`, serves the local ban API | Working, tested |
| `/dashboard` — served directly by `/cli` on one port (JSON API + built UI) | Working, tested |
| Core `/backend` FastAPI service (multi-target aggregation, auth, SQLite, audit log) | **Not built yet.** Everything above works standalone against one target with no core running — that's intentional (see `docs/SPEC.md` §7 trust boundaries), not a workaround. |

The marketing/landing site lives in its own repo now:
[sentinal-landing](https://github.com/SahilSidhu7/sentinal-landing)
(hosted at [sahilsidhu7.github.io/sentinal-landing](https://sahilsidhu7.github.io/sentinal-landing/)) — it isn't part of the monitoring loop and doesn't need to ship alongside this code.

## Install

One line, on any Linux server with `git`:

```bash
curl -fsSL https://sahilsidhu7.github.io/sentinal-landing/install.sh | bash
```

That clones this repo and runs `scripts/install.sh` for you — the only
manual step either way, since bootstrapping Python/pip can't itself be a
`sentinal` command before `sentinal` exists. It creates a `.venv`, installs
`/model` + `/backend` + `/cli` (editable), exports the ONNX embedding
model, and builds the dashboard's static assets. Each step degrades
gracefully and tells you what to do manually if it can't reach the network
or a tool (Docker, Node.js) isn't installed.

Prefer to clone yourself first:

```bash
git clone https://github.com/SahilSidhu7/Sentinal.git
cd Sentinal
./scripts/install.sh
```

Either way, finish with:

```bash
cd Sentinal   # if you used the one-liner
source .venv/bin/activate
sentinal --help
```

Windows/dev: skip both, run the equivalent steps by hand (see
[`cli/README.md`](cli/README.md) "Setup").

**After install, every feature is a `sentinal` command** — building images,
running/stopping containers, tailing logs, scanning, upgrading. There is no
second script or manual docker step in the normal workflow.

## Quick start

```bash
sentinal register --target-id my-app --backend-url http://localhost:8000
sentinal run --target-id my-app --path ./my-app --port 8080:8080
```

No `--image`, no Dockerfile required from you. `sentinal run --path` will:

1. **Build the container itself.** Uses `./my-app/Dockerfile` if you have
   one; otherwise detects your app's stack (`requirements.txt` → Python,
   `package.json` → Node) and generates a Dockerfile — you never write or
   run `docker build` yourself. (`--image some:tag` still works if you'd
   rather run something already built.)
2. Launch the container.
3. Run the startup vulnerability scan (`docs/VULNERABILITY_CHECKLIST.md`)
   and refuse to start on a `critical` finding (`--force` to override).
4. Seed anomaly detection from a pretrained baseline (`--seed-model`,
   default `nginx`) or cold-start on this target's own first 200 log lines
   (`--seed-model none`) — see "Self-improving detection" below.
5. Stream logs into the anomaly pipeline, escalating sustained per-IP
   attack patterns.
6. Serve **the dashboard UI and its JSON API together** on one port
   (`--status-api-port`, default **8765**) — open
   `http://<this-host>:8765` in a browser.
7. Serve the local ban-action API (`--ban-api-port`, default 8787) for
   IP-ban coordination.
8. **Track the running container against `my-app`** — no docker container
   ID to find or paste anywhere:

```bash
sentinal logs --target-id my-app     # tail its output
sentinal stop --target-id my-app     # stop it
sentinal status --target-id my-app   # see everything sentinal knows about it
```

Want to see this whole loop working against a real (deliberately
vulnerable) target first? See
[`../sentinel-demo-app`](https://github.com/SahilSidhu7/sentinel-demo-app) —
a small Flask app + attack-traffic generator built specifically to showcase
every piece of this pipeline end to end:

```bash
git clone https://github.com/SahilSidhu7/sentinel-demo-app.git
sentinal register --target-id demo --backend-url http://localhost:8000
sentinal run --target-id demo --path ./sentinel-demo-app --port 5000:5000 --seed-model none --force
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
| `register` | `--target-id`, `--backend-url` | — | Registers a target, persists its config (backend URL, token, later its container id) to `~/.sentinal/<target_id>.json`. Degrades to a tokenless local registration if core is unreachable. |
| `scan` | `--target-id` | `--volume` (repeatable) | Runs the startup vulnerability scan standalone — no container needs to be running. Good for checking source before deploying it. |
| `run` | `--target-id`, one of `--path`/`--image` | `--port`, `--env`, `--volume` (all repeatable); `--name`; `--force`; `--ban-api-port` (8787); `--status-api-port` (8765); `--batch-size` (50); `--baseline-lines` (200); `--seed-model` (`nginx`); `--retrain-every` (500) | Builds (if `--path`) and launches the container, runs the startup scan, then monitors it for its lifetime — see "Quick start" above. Full option table in `cli/README.md`. |
| `stop` | `--target-id` | — | Stops the target's tracked container. |
| `logs` | `--target-id` | `--follow`/`--no-follow` (default follow) | Tails the target's tracked container's output. |
| `status` | `--target-id` | — | Prints the target's full persisted config as JSON, including its running container id if any. |
| `fim-baseline` | `--root`, `--target-id` | — | (Re)builds the file-integrity baseline hash set for a path, independent of `run`. |
| `serve-ban-api` | one of `--target-id`/`--container-id` | `--host`, `--port` (8787) | Runs the ban-action API standalone — normally started for you inside `run`. |
| `upgrade` | — | `--skip-dashboard-build` | Pulls latest + reinstalls everything (editable), rebuilds the dashboard. |
| `help` | — | — | Same as `--help`. |
| `--version` | — | — | Prints the installed version. |

## Upgrading

```bash
sentinal upgrade
```

or, if the venv isn't active yet / `sentinal` isn't on `PATH`:

```bash
./scripts/upgrade.sh
```

Both do the same thing: `git pull`, reinstall `/model` + `/backend` +
`/cli` editable, rebuild `/dashboard`'s static assets.

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
/backend    vibesentinel_scanner (startup vuln checks) + the not-yet-built
            core FastAPI service
/dashboard  Thin status site, served by /cli (React + Vite + Tailwind)
/docs       Spec + the vulnerability checklist
/scripts    install.sh / upgrade.sh (the one manual bootstrap step and its
            update path — everything after install is a sentinal command)
```

Marketing site: separate repo, [sentinal-landing](https://github.com/SahilSidhu7/sentinal-landing) (also hosts the one-line installer above).

Each folder's README has its team's scope and the cross-folder contracts it
depends on — see `docs/SPEC.md` §11.1 / `TEAM.md`.

## Known limitations

- **Core `/backend` FastAPI service doesn't exist yet** — no multi-target
  aggregation, no auth, no SQLite-backed history across restarts. Every
  command above works fully standalone against one target; core-facing
  calls (`register`, event forwarding) are best-effort and silently degrade
  if core isn't running.
- **Windows dev machines**: `--volume`/`--path`'s FIM watcher and
  auto-mount split a host path on `:` to separate host/container sides —
  correct for Linux host paths (this project's actual deployment target)
  but breaks on `C:\...`-style paths, which have their own colon. Not
  fixed, since the product doesn't target Windows hosts — see
  `cli/README.md`'s "Known platform limitation".
- **Dependency-CVE checks need outbound network access** (OSV.dev) — they
  degrade to "not checked this run" rather than failing the scan when
  offline, per the checklist doc.
