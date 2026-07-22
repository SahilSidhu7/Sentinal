# /dashboard — Local Status Site (Team D)

Branch: `dashboard` · Spec: `docs/SPEC.md` §8

Owns: **dashboard management** for single-box operators — a thin, localhost-only status site served *by* `/cli` on the monitored host itself.

## Scope
- Shows local target health, recent findings/attack events, ban status — for someone running only the CLI/agent on one box, without standing up the full `/backend` + `/frontend` stack.
- Reads the same findings/attack-event JSON shape the core backend API uses (`docs/SPEC.md` §6), so components can be shared with `/frontend` where practical (both Recharts + Tailwind).
- Served locally by `/cli` (e.g. a small embedded HTTP server or a static build the CLI hosts) — coordinate the serving mechanism with Team B.
- **Auth note:** SPEC.md's stated scope for this module is no-auth (single trusted operator already on the box). The UI now includes a login screen in front of it by product decision — it's a fully local, client-side gate (no network call, no JWT, no `/backend` dependency), not the real auth `/frontend` implements. Treat it as a UX gate, not a security boundary.

## Stack
Same as `/frontend`: React/Vite/Tailwind/Recharts, kept intentionally thin (no multi-target, no real backend auth).

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

Rebuilt from the `stitch_sentinel_security_dashboard` design export (left untouched at the repo root as reference) — 5 screens, componentized instead of duplicated static HTML.

- **Pages**: `Login` (local-only gate, see Auth note above), `Activity` (real-time feed + intelligence panel), `Security` (score hero + issues + bento stats), `Containers`, `Settings`. Routing behind `RequireAuth`; `/login` is the only public route.
- **Shared components**: `TopNav` (glass nav bar with an animated sliding underline tracking the active tab), `GlassPanel`, `StatusDot`, `SeverityBadge`, `ProgressBar`, `MaterialIcon`.
- **Design tokens**: transcribed 1:1 from the export's inline `tailwind.config` blocks into a Tailwind v4 `@theme` in `src/index.css` (colors, Inter/JetBrains Mono type scale, radii, spacing). Glassmorphism border alpha was drifting (0.05/0.08/0.1) across the original 3 screens that defined it — unified to 0.08 per `obsidian_sentinel/DESIGN.md`'s stated value.
- **`src/lib/api.js`** — fetches `/api/score`, `/api/findings`, `/api/attacks`, `/api/settings` and connects to `/ws/live`, all against `/cli`'s local feed (proxied via `VITE_AGENT_URL`, default `http://localhost:8765`); falls back to `src/lib/mockData.js` (shaped per SPEC §5) if the agent isn't reachable yet.
- **`src/lib/auth.jsx`** — fully client-side login (no fetch attempt, no `/backend` dependency), matching the exported prototype's simulated-delay behavior.
- **Containers screen has no backing table/endpoint in SPEC.md** (§5/§6 only define findings/attack_events/bans/audit_log) — it's intentionally mock-only (`mockContainers`), flagged in code, not wired to any assumed API contract.
- Two decorative images from the original export (the "Global Origin Points" map texture and the operator headshot, both hotlinked to a temporary Google-hosted AI-image CDN) were replaced with plain placeholder blocks rather than re-hotlinked — everything else visual (colors, layout, animations, copy) is unchanged.
