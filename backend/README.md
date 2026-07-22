# /backend — Core API (owner: Sahil)

Branch: `main` (shared core, not a per-teammate branch) · Spec: `docs/SPEC.md` §3 (Modules 1,2,5,7,8), §6

Owns: **vulnerability test** — the scanner + FIM + fusion/scoring + auto-response + audit log, plus the API surface every other folder talks to.

## Scope
- Secret/dependency scanner (regex + entropy, OSV.dev CVE lookups), FIM baseline hashing.
- Explainer (static rule-template lookup), Fusion/Scoring engine (security score).
- Auto-response (audit writes, manual-confirm ban trigger), Audit Log (chained hash).
- REST + WebSocket API (`docs/SPEC.md` §6) consumed by `/frontend`, `/cli`, `/dashboard`.
- Imports `/model`'s `LogPipeline` as a library for any server-side scoring needs; primary anomaly detection runs in `/cli` on the monitored host, not here.

## Stack
Python 3.11 + FastAPI, SQLite, Redis (fallback: in-memory dict + asyncio locks).

## What exists today

`vibesentinel_scanner/` is real and installable (`pip install -e ./backend`) —
the secrets/dependency-CVE/docker-misconfig/weak-credential scanner from
Module 1, see `docs/VULNERABILITY_CHECKLIST.md` for the full check list and
`docs/SPEC.md` §5 for the `Finding` shape. `/cli` imports it directly
(`cli/sentinal/scanner.py`) and runs it locally at `sentinal run`/`scan` time
— **the FastAPI service (`POST /targets/{id}/scan`, the rest of §6's API
surface, SQLite persistence, Redis, auth, audit log) doesn't exist yet.**
Building that service around this package (rather than duplicating the
checks) is the next step here.

## Setup (once scaffolded)
```
cd backend
pip install -e .            # installs vibesentinel_scanner
uvicorn app.main:app --reload   # not yet implemented — see "What exists today"
```
