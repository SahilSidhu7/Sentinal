# /dashboard — Local Status Site (Team D)

Branch: `dashboard` · Spec: `docs/SPEC.md` §8

Owns: **dashboard management** for single-box operators — a thin, localhost-only, no-auth status site served *by* `/cli` on the monitored host itself.

## Scope
- Shows local target health, recent findings/attack events, ban status — for someone running only the CLI/agent on one box, without standing up the full `/backend` + `/frontend` stack.
- Reads the same findings/attack-event JSON shape the core backend API uses (`docs/SPEC.md` §6), so components can be shared with `/frontend` where practical (both Recharts + Tailwind).
- Served locally by `/cli` (e.g. a small embedded HTTP server or a static build the CLI hosts) — coordinate the serving mechanism with Team B.

## Stack
Same as `/frontend`: React/Vite/Tailwind/Recharts, kept intentionally thin (no auth, no multi-target).

## Contract you depend on
- The findings/attack-event JSON shape from `/cli`'s local feed — confirm the exact fields with Team B before building views around them.
- Coordinate with `/frontend` (Team A) on any shared components/theme.

## Getting started

```
cd dashboard
npm install
npm run dev      # dev server on :5173, proxies /api to VITE_AGENT_URL (default http://localhost:8765)
npm run build    # static build for /cli to serve
npm run lint      # oxlint
```

## Current scaffold

- Vite + React 19 + Tailwind v4 (`@tailwindcss/vite`) + Recharts + react-router-dom.
- Pages: `Overview` (score trend, live feed, open findings), `Findings` (table + inline detail/dismiss), `Attacks` (table + manual ban).
- `src/lib/api.js` — fetches `/api/score`, `/api/findings`, `/api/attacks`, `/api/bans` and connects to `/ws/live`; falls back to `src/lib/mockData.js` if the agent isn't reachable yet, so UI work isn't blocked on `/cli`.
- No auth, no build tooling beyond Vite — keep it thin per the spec.
