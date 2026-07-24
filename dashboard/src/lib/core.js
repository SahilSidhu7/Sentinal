// Client for the hosted management core (backend/vibesentinel_core). Talks to
// it directly (CORS is open in dev) rather than through the /api proxy the
// legacy agent pages use, so the two wiring paths stay independent during the
// pivot. Point VITE_CORE_URL at the core backend if it isn't on :8000.

const CORE = import.meta.env.VITE_CORE_URL || 'http://localhost:8000'
const WS_BASE = CORE.replace(/^http/, 'ws')

export async function listProjects() {
  const res = await fetch(`${CORE}/api/projects`)
  if (!res.ok) throw new Error(`list projects -> ${res.status}`)
  return res.json()
}

export async function createProject(name, demo = false) {
  const res = await fetch(`${CORE}/api/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name || null, demo }),
  })
  if (!res.ok) throw new Error(`create project -> ${res.status}`)
  return res.json()
}

export async function deleteProject(id) {
  await fetch(`${CORE}/api/projects/${id}`, { method: 'DELETE' })
}

export const terminalURL = (id, which) => `${WS_BASE}/api/projects/${id}/terminal/${which}`
export const alertsURL = (id) => `${WS_BASE}/api/projects/${id}/alerts`
