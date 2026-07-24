// Client for the hosted management core (backend/vibesentinel_core). Talks to
// it directly (CORS is open in dev) rather than through the /api proxy the
// legacy agent pages use, so the two wiring paths stay independent during the
// pivot. Point VITE_CORE_URL at the core backend if it isn't on :8000.

// Default to the origin the dashboard is served from — the core serves the UI
// and the API together, so they're always same-origin (works behind any
// domain/reverse-proxy/TLS without config). Override only for a split dev setup
// (e.g. Vite on :5173 hitting the core on :8000) via VITE_CORE_URL.
const CORE = import.meta.env.VITE_CORE_URL || window.location.origin
const WS_BASE = CORE.replace(/^http/, 'ws') // http->ws, https->wss
const TOKEN_KEY = 'sentinel_local_token' // same key the login flow (lib/auth) stores

const token = () => localStorage.getItem(TOKEN_KEY)
const authHeaders = () => {
  const t = token()
  return t ? { Authorization: `Bearer ${t}` } : {}
}

export async function listProjects() {
  const res = await fetch(`${CORE}/api/projects`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`list projects -> ${res.status}`)
  return res.json()
}

export async function createProject(name, demo = false) {
  const res = await fetch(`${CORE}/api/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ name: name || null, demo }),
  })
  if (!res.ok) throw new Error(await errorDetail(res, 'create project'))
  return res.json()
}

// Pull the server's `detail` (e.g. the Docker-permission fix) into the thrown
// error so the UI shows something actionable instead of a bare status code.
async function errorDetail(res, action) {
  try {
    const body = await res.json()
    if (body && body.detail) return body.detail
  } catch {
    /* non-JSON response */
  }
  return `${action} -> ${res.status}`
}

export async function deleteProject(id) {
  await fetch(`${CORE}/api/projects/${id}`, { method: 'DELETE', headers: authHeaders() })
}

// Browsers can't set headers on a WebSocket, so the session token rides the
// query string (the core validates it before streaming anything).
const wsAuth = () => (token() ? `?token=${encodeURIComponent(token())}` : '')
export const terminalURL = (id, which) => `${WS_BASE}/api/projects/${id}/terminal/${which}${wsAuth()}`
export const alertsURL = (id) => `${WS_BASE}/api/projects/${id}/alerts${wsAuth()}`
