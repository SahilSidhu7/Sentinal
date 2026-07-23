// Client for /cli's local status feed (docs/SPEC.md §6, §8). Real fetch
// first; falls back to mockData.js when /cli isn't reachable yet so the UI
// stays usable during development. Field shapes mirror the shared
// findings/attack-event contract used by /backend and /cli.

import { mockScore, mockFindings, mockAttackEvents, mockSettings, mockContainers } from './mockData'

const TOKEN_KEY = 'sentinel_local_token'

function authHeaders() {
  const token = localStorage.getItem(TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function getJSON(path, fallback) {
  try {
    const res = await fetch(path, { headers: authHeaders() })
    if (!res.ok) throw new Error(`${path} -> ${res.status}`)
    return await res.json()
  } catch (err) {
    console.warn(`[dashboard] falling back to mock data for ${path}:`, err.message)
    return fallback
  }
}

export async function login(password) {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  })
  if (!res.ok) {
    throw new Error(res.status === 401 ? 'Incorrect password' : `login -> ${res.status}`)
  }
  const data = await res.json()
  return data.token
}

export async function verifyToken(token) {
  try {
    const res = await fetch('/api/auth/verify', { headers: { Authorization: `Bearer ${token}` } })
    return res.ok
  } catch {
    return false
  }
}

export function getScore() {
  return getJSON('/api/score', mockScore)
}

export function getFindings() {
  return getJSON('/api/findings', mockFindings)
}

export function getAttacks() {
  return getJSON('/api/attacks', mockAttackEvents)
}

export function getSettings() {
  return getJSON('/api/settings', mockSettings)
}

export function getContainers() {
  return getJSON('/api/containers', mockContainers)
}

export async function saveSettings(settings) {
  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(settings),
    })
    if (!res.ok) throw new Error(`settings -> ${res.status}`)
    return await res.json()
  } catch (err) {
    console.warn('[dashboard] settings save failed (agent unreachable):', err.message)
    return settings
  }
}

export async function respondToAttack(id, action) {
  try {
    await fetch(`/api/attacks/${id}/${action}`, { method: 'POST', headers: authHeaders() })
  } catch (err) {
    console.warn(`[dashboard] ${action} failed (agent unreachable):`, err.message)
  }
}

export function connectLiveFeed(onEvent) {
  let ws
  try {
    const token = localStorage.getItem(TOKEN_KEY)
    const query = token ? `?token=${encodeURIComponent(token)}` : ''
    ws = new WebSocket(`ws://${window.location.host}/ws/live${query}`)
    ws.onmessage = (msg) => {
      try {
        onEvent(JSON.parse(msg.data))
      } catch {
        // ignore malformed frames
      }
    }
    ws.onerror = () => {}
  } catch {
    return () => {}
  }
  return () => ws?.close()
}
