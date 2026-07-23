# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Code exists — this is no longer pre-build. `/backend` (scanner lib + FastAPI core), `/cli` (sentinel-agent), `/model` (Drain3+ONNX+IForest, with trained artifacts), and `/dashboard` (React) are all scaffolded and partly working. `docs/SPEC.md` is the original spec; parts are now superseded by the pivot below.

### Core pivot (2026-07-23): hosted management platform

The original model — CLI dockerizes a target and tails *its* logs — is being replaced by a **hosted management system**. Each *project* is an isolated Linux container ("environment") the user drives through **two browser terminals**: a *server* terminal (run your app) and a *tests* terminal (run tests, watch alerts). A short access id is auto-generated on creation when the user gives no name. The model watches the **server terminal's live output** in real time; everything else is driven from the dashboard.

New core loop: **Create env (auto id) → 2 web terminals (server / tests) → model taps server output → live alerts → dashboard**

- New core package: `backend/vibesentinel_core/` (FastAPI). `main.py` (REST + terminal/alert websockets), `environment.py` (per-project Docker container + async PTY bridge via `docker exec`), `monitor.py` (tees server output into `vibesentinel_model.LogPipeline`), `ids.py`, `env_image/` (Ubuntu image + `ptybroker.py` in-container PTY + `demo_server.py`). Run: `uvicorn vibesentinel_core.main:app` (install `pip install -e "./backend[core]"`).
- Frontend: `dashboard/src/pages/Environment.jsx` + `Terminal.jsx` (xterm.js panes), `lib/core.js` (talks to core at `VITE_CORE_URL`, default :8000). Route `/environments` is now the dashboard landing page.
- Real PTY lives **inside** the container (`ptybroker.py`) so it works from a Windows host; the host only pipes bytes over `docker exec -i`. Resize rides the byte pipe as an APC frame `\x1b_RESIZE:cols:rows\x1b\\`.
- Status: vertical slice — create→id→2 terminals→live anomaly alert. Backend + frontend build/import clean. **Live end-to-end run was blocked by a broken local Docker Desktop engine** where `docker exec`/`inspect` return "No such container" for containers `docker ps` shows running; fix is restarting Docker Desktop (`wsl --shutdown` then relaunch). `is_running()` uses `docker ps`, not `inspect`, to sidestep that class of inconsistency.

## What this project is

VibeSentinel is a full-stack security monitoring platform for local machines and small self-hosted servers. It watches a target (folder, repo, or container), scans it for security issues, detects live attacks via a local Drain3 + ONNX embedding + Isolation Forest pipeline (no LLM anywhere in the detection path), visualizes risk on a live dashboard, and takes safe, human-approved response actions (including opt-in auto IP-banning under strict conditions).

Core loop: **Watch → Scan → Detect (Drain3 + ONNX + IsolationForest) → Show (Dashboard) → Act (auto-response)**

The full spec — architecture diagram, data model, API surface, and module-by-module design — lives in `docs/SPEC.md`. Read it before implementing any module; this file only summarizes the parts future Claude instances need to keep straight across sessions.

## Planned tech stack (from spec)

| Layer | Choice |
|---|---|
| Backend API | Python 3.11 + FastAPI (async, WebSocket) |
| Event storage | SQLite (swappable to Postgres later) |
| Cache/state | Redis, with in-memory (dict + asyncio locks) fallback if unreachable |
| Frontend | React + Vite + Tailwind + Recharts |
| CLI / sentinel-agent | Python (Typer/Click) |
| Finding explanations | Static rule-template metadata, rendered per finding (no LLM) |
| Log template parsing | Drain3 |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` via ONNX Runtime (no PyTorch/transformers) |
| Anomaly detection | Isolation Forest (scikit-learn) on template embeddings — fully local, no LLM calls |
| File watching | `watchdog` |
| Packet/log parsing | Scapy (optional, mock mode if unprivileged) + regex log parsers |
| Auth | JWT, single-admin MVP, bcrypt password hashing |
| Background jobs | `asyncio` tasks / `APScheduler` |
| Containerization | Docker + docker-compose (core stack), separate `Dockerfile.agent` for the sentinel-agent |

## Distribution & install (how `sentinal` ships)

The `sentinal` CLI ships as a **self-contained one-file Linux binary** (x86_64 +
aarch64), built with PyInstaller on CI and attached to GitHub Releases. End users
install with a one-liner (`curl … scripts/install.sh | bash`) that downloads the
binary (or the `.deb`) — **no repo clone, no venv, no editable installs** in the
user path. `sentinal upgrade` re-runs the installer when frozen; from a source
checkout it still does `git pull` + editable reinstall (dev workflow).

Because the binary is frozen, data files are resolved through resource helpers,
not raw `__file__` paths — do NOT reintroduce checkout-relative paths:
- Read-only shipped artifacts (ONNX model, pretrained joblib models, drain3
  seeds, `drain3_config.ini`, dashboard `dist/`) come from the bundle via
  `vibesentinel_model._resources` / `sentinal._resources` (`sys._MEIPASS` when
  frozen, `__file__` from source, env override).
- Per-target state the agent *writes* (a target's own trained model, live drain3
  state) goes to a user-writable data dir (`SENTINAL_DATA_DIR` /
  `~/.local/share/sentinal`), never into the bundle (it's read-only/ephemeral).
- The frozen binary spawns its background `monitor` as `sys.executable monitor …`
  (the binary + subcommand), not `python -m sentinal` — see `app.py`.

Build/release lives in `/packaging` (`sentinal.spec`, `build_binary.sh`,
`build_deb.sh`) and `.github/workflows/release.yml`. The ONNX model is exported
during the build (not committed); torch/transformers/optimum are excluded from
the binary (export-only deps).

## Architecture (core concepts)

- **Four-team project split** (`docs/SPEC.md` §11.1): `/frontend` (main dashboard), `/cli` (sentinel-agent CLI), `/model` (Drain3 + ONNX embedding + Isolation Forest train/detect), `/dashboard` (thin localhost status site shipped alongside the CLI). Plus shared `/backend` (FastAPI core) and `/docs`. Keep the cross-team contract points in §11.1 stable (`/model`'s `train()`/`detect()` signatures, the shared findings/attack-event JSON shape) so the four tracks can build in parallel without blocking each other.
- **Two deployable units**: the core backend+frontend (runs via `docker-compose up`), and a separate minimal **sentinel-agent** (`/cli` + `/model`, containerized as `vibesentinel/agent`) users deploy alongside their own servers. The agent tails logs, runs the Drain3+ONNX+IsolationForest pipeline *locally*, and ships only structured findings/scores to the core backend — raw logs never leave the user's infrastructure. This raw-logs-never-leave-the-host boundary is a deliberate trust/privacy property; do not build features that would require the agent to forward raw log lines to the core.
- **Pipeline for every finding**: source module (scanner / FIM / log monitor / anomaly engine) → Explainer (static rule-template lookup, cached by `(finding_type, normalized_snippet, severity)` hash) → Fusion/Scoring Engine (weighted deductions from 100, with correlation boosts for related findings in the same time window) → Dashboard (REST + WebSocket live feed).
- **No LLM anywhere in the detection or explanation path.** High-volume log lines are parsed into templates by Drain3, embedded with `all-MiniLM-L6-v2` via ONNX Runtime (PyTorch/`transformers` explicitly excluded — CPU-only, must fit under a 150MB memory budget per target), and scored with a per-target Isolation Forest trained on that target's own rolling "normal" traffic (`train()`/`detect()` in `/model`, artifacts persisted as `log_anomaly_model.joblib`). Escalated Attack Events resolve against the same static rule-template table as regular findings — no model-serving runtime, no network dependency for detection.
- **IP banning is agent-local, never core-backend-initiated.** The core backend can only request a ban via a narrow API the agent itself exposes (`POST /agent/actions/ban {ip, ttl}`), scoped to that agent's own container network namespace, and only for IPs the core has itself flagged. Default is manual-confirm; auto-ban is opt-in per-target and requires sustained high-confidence anomaly scores. Bans are TTL-based with manual "make permanent" / "unban" controls.
- **Audit log is append-only with a chained hash** (`prev_hash` → `entry_hash` per entry) so tampering is at least detectable. Every finding lifecycle event and every action (ban, unban, dismiss, fix-applied) must be written here — no application-level UPDATE/DELETE.
- **Endpoint/loophole detection (§6.2) is passive-observation only** — derived from traffic already flowing through the agent, never active probing/exploitation of third-party infrastructure. Preserve this boundary; it's what keeps the feature legal-by-default for self-hosted use.

## Explicitly mocked / environment-dependent pieces

When implementing, these must degrade gracefully rather than fail hard — see spec §13:
- Scapy packet sniffing requires elevated privileges; falls back to labeled mock/sample data if unavailable.
- Real SMTP email is mocked/test-only unless the user supplies real credentials.
- OSV.dev CVE lookups need outbound network access; degrade to "unknown, network unavailable" rather than failing the scan.
