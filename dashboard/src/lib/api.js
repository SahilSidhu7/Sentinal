// Client for the local status feed served by /cli (docs/SPEC.md §6, §8).
// Shape here mirrors the shared findings/attack-event contract used by
// /backend and /cli — confirm exact field names with Team B before relying
// on anything beyond what's listed in mockData.js.

import { mockScore, mockFindings, mockAttacks, mockBans } from './mockData'

const BASE = ''

async function getJSON(path, fallback) {
  try {
    const res = await fetch(`${BASE}${path}`)
    if (!res.ok) throw new Error(`${path} -> ${res.status}`)
    return await res.json()
  } catch (err) {
    console.warn(`[dashboard] falling back to mock data for ${path}:`, err.message)
    return fallback
  }
}

export function getScore() {
  return getJSON('/api/score', mockScore)
}

export function getFindings() {
  return getJSON('/api/findings', mockFindings)
}

export function getFinding(id) {
  return getJSON(`/api/findings/${id}`, mockFindings.find((f) => f.id === id) ?? null)
}

export function getAttacks() {
  return getJSON('/api/attacks', mockAttacks)
}

export function getBans() {
  return getJSON('/api/bans', mockBans)
}

export async function dismissFinding(id) {
  try {
    await fetch(`/api/findings/${id}/dismiss`, { method: 'POST' })
  } catch (err) {
    console.warn('[dashboard] dismiss failed (agent unreachable):', err.message)
  }
}

export async function banIp(attackId, ttlSeconds) {
  try {
    await fetch(`/api/attacks/${attackId}/ban`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ttl: ttlSeconds }),
    })
  } catch (err) {
    console.warn('[dashboard] ban failed (agent unreachable):', err.message)
  }
}

// Live feed over the agent's local WS (falls back to null if unreachable —
// callers should keep rendering whatever they last polled via REST).
export function connectLiveFeed(onEvent) {
  let ws
  try {
    ws = new WebSocket(`ws://${window.location.host}/ws/live`)
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
