// Client for /cli's local status feed (docs/SPEC.md §6, §8). Real fetch
// first; falls back to mockData.js when /cli isn't reachable yet so the UI
// stays usable during development. Field shapes mirror the shared
// findings/attack-event contract used by /backend and /cli.

import { mockScore, mockFindings, mockAttackEvents, mockSettings, mockContainers } from './mockData'

async function getJSON(path, fallback) {
  try {
    const res = await fetch(path)
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
      headers: { 'Content-Type': 'application/json' },
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
    await fetch(`/api/attacks/${id}/${action}`, { method: 'POST' })
  } catch (err) {
    console.warn(`[dashboard] ${action} failed (agent unreachable):`, err.message)
  }
}

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
