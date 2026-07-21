# /frontend — Main Dashboard (Team A)

Branch: `frontend` · Spec: `docs/SPEC.md` §3 (Module 6), §6, §8

Owns: **dashboard management** — the full multi-target web dashboard.

## Scope
- Login (JWT), Overview (security score gauge, findings-by-severity chart, live activity feed), Findings list + detail view, Live feed (WebSocket), Attacks/Live Monitoring view, Settings.
- Talks to `/backend` only, over REST + WebSocket (`docs/SPEC.md` §6). No direct dependency on `/model` or `/cli`.

## Stack
React + Vite + Tailwind + Recharts.

## Setup (once scaffolded)
```
cd frontend
npm install
npm run dev
```

## Contract you depend on
Backend API surface in `docs/SPEC.md` §6 (`/findings`, `/score`, `/attacks`, `/ws/live`, etc). If backend hasn't stood these up yet, mock them locally — don't block on `/backend` completion to start on layout/components.
