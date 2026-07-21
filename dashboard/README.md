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
