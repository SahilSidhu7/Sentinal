import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { alertsURL, createProject, deleteProject, listProjects, terminalURL } from '../lib/core'
import TerminalPane from './Terminal'

// The management workspace: pick or create a project, then drive its isolated
// Linux environment through two terminals — left runs your server, right runs
// tests — while the model watches the server terminal's live output and raises
// alerts into the feed below.
export default function Environment() {
  const [projects, setProjects] = useState([])
  const [selected, setSelected] = useState(null)
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [searchParams] = useSearchParams()

  const refresh = useCallback(() => {
    listProjects()
      .then(setProjects)
      .catch((e) => setError(e.message))
  }, [])

  useEffect(refresh, [refresh])

  // Deep-link from the overview (?p=<id>) opens that workspace directly.
  useEffect(() => {
    const wanted = searchParams.get('p')
    if (wanted && !selected) {
      const match = projects.find((x) => x.id === wanted)
      if (match) setSelected(match)
    }
  }, [searchParams, projects, selected])

  async function onCreate(e) {
    e.preventDefault()
    setCreating(true)
    setError('')
    try {
      const p = await createProject(name.trim())
      setName('')
      setProjects((prev) => [...prev.filter((x) => x.id !== p.id), p])
      setSelected(p)
    } catch (err) {
      setError(err.message)
    } finally {
      setCreating(false)
    }
  }

  async function onDelete(id) {
    await deleteProject(id)
    if (selected?.id === id) setSelected(null)
    refresh()
  }

  return (
    <main className="max-w-[1440px] mx-auto px-gutter pt-24 pb-16">
      <div className="flex items-start gap-8">
        {/* Sidebar: projects + create */}
        <aside className="w-72 shrink-0">
          <h1 className="font-headline-sm text-headline-sm font-bold mb-4">Environments</h1>
          <form onSubmit={onCreate} className="mb-4">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="project name (optional)"
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary"
            />
            <button
              type="submit"
              disabled={creating}
              className="mt-2 w-full bg-primary text-black font-label-caps text-label-caps rounded-lg py-2 disabled:opacity-50"
            >
              {creating ? 'Provisioning…' : 'Create environment'}
            </button>
          </form>
          {error && <p className="text-red-400 text-xs mb-3">{error}</p>}
          <ul className="space-y-1">
            {projects.map((p) => (
              <li key={p.id}>
                <button
                  onClick={() => setSelected(p)}
                  className={`w-full text-left px-3 py-2 rounded-lg border transition-colors ${
                    selected?.id === p.id
                      ? 'border-primary bg-primary/10'
                      : 'border-transparent hover:bg-white/5'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium truncate">{p.name}</span>
                    <span className={`w-2 h-2 rounded-full ${p.running ? 'bg-green-400' : 'bg-white/20'}`} />
                  </div>
                  <code className="text-xs text-on-surface-variant">id: {p.id}</code>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        {/* Workspace */}
        <section className="flex-1 min-w-0">
          {selected ? (
            <Workspace key={selected.id} project={selected} onDelete={() => onDelete(selected.id)} />
          ) : (
            <div className="h-[60vh] flex items-center justify-center text-on-surface-variant">
              Select or create an environment to open its terminals.
            </div>
          )}
        </section>
      </div>
    </main>
  )
}

function Workspace({ project, onDelete }) {
  const [alerts, setAlerts] = useState([])
  const [monitoring, setMonitoring] = useState(null)
  const [dangerOnly, setDangerOnly] = useState(false)
  const alertWs = useRef(null)

  useEffect(() => {
    const ws = new WebSocket(alertsURL(project.id))
    alertWs.current = ws
    ws.onmessage = (ev) => {
      const a = JSON.parse(ev.data)
      if (a.type === 'status') {
        setMonitoring(a.monitoring)
        return
      }
      setAlerts((prev) => [a, ...prev].slice(0, 100))
    }
    return () => ws.close()
  }, [project.id])

  // onOutput must be stable so the server pane's effect doesn't re-run.
  const noop = useRef(() => {}).current

  const dangerCount = alerts.filter((a) => a.type === 'attack').length
  const shown = dangerOnly ? alerts.filter((a) => a.type === 'attack') : alerts

  return (
    <div>
      {project.is_demo && (
        <div className="mb-4 rounded-lg border border-primary/40 bg-primary/5 p-3 text-sm">
          <span className="font-bold text-primary">Demo project.</span> In the{' '}
          <span className="text-on-surface">Server</span> terminal run{' '}
          <code className="text-primary">python3 /opt/demo_server.py</code>, then in{' '}
          <span className="text-on-surface">Tests</span> run{' '}
          <code className="text-primary">python3 /opt/traffic.py</code> — watch the alert feed below light up.
        </div>
      )}
      <header className="flex items-center justify-between mb-4">
        <div>
          <h2 className="font-headline-sm text-headline-sm font-bold">{project.name}</h2>
          <code className="text-sm text-on-surface-variant">access id: {project.id}</code>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${monitoring ? 'bg-green-400 animate-pulse' : 'bg-yellow-400'}`} />
            {monitoring == null ? 'connecting…' : monitoring ? 'model live' : 'monitor off'}
          </span>
          <button onClick={onDelete} className="text-xs text-red-400 hover:underline">
            Destroy
          </button>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-4 h-[52vh]">
        <div className="flex flex-col">
          <div className="font-label-caps text-label-caps text-on-surface-variant mb-1">Server · monitored</div>
          <div className="flex-1 min-h-0">
            <TerminalPane url={terminalURL(project.id, 'server')} onOutput={noop} />
          </div>
        </div>
        <div className="flex flex-col">
          <div className="font-label-caps text-label-caps text-on-surface-variant mb-1">Tests</div>
          <div className="flex-1 min-h-0">
            <TerminalPane url={terminalURL(project.id, 'tests')} />
          </div>
        </div>
      </div>

      <div className="mt-6">
        <div className="flex items-center justify-between mb-2">
          <span className="font-label-caps text-label-caps text-on-surface-variant">
            Live monitoring alerts ({shown.length}{dangerOnly ? ' danger' : ''})
          </span>
          <button
            onClick={() => setDangerOnly((v) => !v)}
            className={`flex items-center gap-2 text-xs px-3 py-1 rounded-full border transition-colors ${
              dangerOnly ? 'border-red-500/60 bg-red-500/10 text-red-300' : 'border-white/10 text-on-surface-variant hover:text-on-surface'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${dangerOnly ? 'bg-red-400' : 'bg-white/30'}`} />
            Danger only{dangerCount ? ` (${dangerCount})` : ''}
          </button>
        </div>
        <div className="bg-white/[0.03] border border-white/10 rounded-lg divide-y divide-white/5 max-h-64 overflow-y-auto">
          {shown.length === 0 && (
            <p className="text-sm text-on-surface-variant p-4">
              {dangerOnly
                ? 'No danger alerts. Attacks (SQLi/XSS/traversal/…) will show here.'
                : 'No anomalies yet. Run a server on the left and hit it from the right.'}
            </p>
          )}
          {shown.map((a, i) => (
            <div key={i} className="flex items-start gap-3 p-3 text-sm">
              <span
                className={`shrink-0 mt-0.5 px-2 py-0.5 rounded text-xs font-bold ${
                  a.type === 'attack' ? 'bg-red-500/20 text-red-300' : 'bg-yellow-500/20 text-yellow-300'
                }`}
              >
                {a.matched_signature || a.type}
              </span>
              <div className="min-w-0">
                <code className="block truncate text-on-surface">{a.line}</code>
                <span className="text-xs text-on-surface-variant">score {a.severity_score}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
