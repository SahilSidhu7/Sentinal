# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repository is **pre-build**. It currently contains only the product/engineering spec (`docs/SPEC.md`) — no backend, frontend, agent, or infra code exists yet. There are no build/lint/test commands to run because nothing has been scaffolded. Before running or referencing any tooling commands, check whether the relevant code has actually been created; do not assume commands from the target stack (e.g. `pytest`, `npm run dev`) work until the corresponding project files exist.

When starting implementation, follow the build order in `docs/SPEC.md` §12 (Foundation → scanner/FIM → AI explainer/fusion → dashboard → log monitor/anomaly pipeline → auto-response/IP ban → sentinel-agent → audit hardening → endpoint detection), and create the directory layout specified in §11: `/backend`, `/frontend`, `/agent`, `/docs`.

## What this project is

VibeSentinel is a full-stack, AI-powered security monitoring platform for local machines and small self-hosted servers. It watches a target (folder, repo, or container), scans it for security issues, explains findings in plain English via a local LLM, visualizes risk on a live dashboard, and takes safe, human-approved response actions (including opt-in auto IP-banning under strict conditions).

Core loop: **Watch → Scan → Explain (AI) → Show (Dashboard) → Act (auto-response)**

The full spec — architecture diagram, data model, API surface, and module-by-module design — lives in `docs/SPEC.md`. Read it before implementing any module; this file only summarizes the parts future Claude instances need to keep straight across sessions.

## Planned tech stack (from spec)

| Layer | Choice |
|---|---|
| Backend API | Python 3.11 + FastAPI (async, WebSocket) |
| Event storage | SQLite (swappable to Postgres later) |
| Cache/state | Redis, with in-memory (dict + asyncio locks) fallback if unreachable |
| Frontend | React + Vite + Tailwind + Recharts |
| AI explanation | Ollama (local LLM, e.g. `llama3.2` / `qwen2.5:3b`) |
| Anomaly detection | Local MiniLM embeddings + Isolation Forest (scikit-learn) — not per-line LLM calls |
| File watching | `watchdog` |
| Packet/log parsing | Scapy (optional, mock mode if unprivileged) + regex log parsers |
| Auth | JWT, single-admin MVP, bcrypt password hashing |
| Background jobs | `asyncio` tasks / `APScheduler` |
| Containerization | Docker + docker-compose (core stack), separate `Dockerfile.agent` for the sentinel-agent |

## Architecture (core concepts)

- **Two deployable units**: the core backend+frontend+dashboard (runs via `docker-compose up`), and a separate minimal **sentinel-agent** container (`vibesentinel/agent`) users deploy alongside their own servers. The agent tails logs, runs the embedding+anomaly pipeline *locally*, and ships only structured findings/scores to the core backend — raw logs never leave the user's infrastructure. This raw-logs-never-leave-the-host boundary is a deliberate trust/privacy property; do not build features that would require the agent to forward raw log lines to the core.
- **Pipeline for every finding**: source module (scanner / FIM / log monitor / anomaly engine) → AI Explainer (Ollama, cached by `(finding_type, normalized_snippet, severity)` hash) → Fusion/Scoring Engine (weighted deductions from 100, with correlation boosts for related findings in the same time window) → Dashboard (REST + WebSocket live feed).
- **Anomaly detection is not per-line LLM inference.** High-volume log lines are normalized into templates, embedded with a compact sentence-embedding model (MiniLM), and scored with a per-target Isolation Forest trained on that target's own rolling "normal" traffic. Only *escalated* Attack Events get sent to Ollama for a plain-English summary — this is what keeps the pipeline viable on modest hardware against noisy production logs.
- **IP banning is agent-local, never core-backend-initiated.** The core backend can only request a ban via a narrow API the agent itself exposes (`POST /agent/actions/ban {ip, ttl}`), scoped to that agent's own container network namespace, and only for IPs the core has itself flagged. Default is manual-confirm; auto-ban is opt-in per-target and requires sustained high-confidence anomaly scores. Bans are TTL-based with manual "make permanent" / "unban" controls.
- **Audit log is append-only with a chained hash** (`prev_hash` → `entry_hash` per entry) so tampering is at least detectable. Every finding lifecycle event and every action (ban, unban, dismiss, fix-applied) must be written here — no application-level UPDATE/DELETE.
- **Endpoint/loophole detection (§6.2) is passive-observation only** — derived from traffic already flowing through the agent, never active probing/exploitation of third-party infrastructure. Preserve this boundary; it's what keeps the feature legal-by-default for self-hosted use.

## Explicitly mocked / environment-dependent pieces

When implementing, these must degrade gracefully rather than fail hard — see spec §13:
- Scapy packet sniffing requires elevated privileges; falls back to labeled mock/sample data if unavailable.
- Real SMTP email is mocked/test-only unless the user supplies real credentials.
- OSV.dev CVE lookups need outbound network access; degrade to "unknown, network unavailable" rather than failing the scan.
- Ollama requires a local install with a pulled model; backend must detect unavailability and surface an "AI explainer offline" state rather than blocking the rest of the pipeline.
