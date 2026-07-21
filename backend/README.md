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

## Setup (once scaffolded)
```
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
