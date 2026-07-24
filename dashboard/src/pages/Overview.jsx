import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createProject, listProjects } from '../lib/core'

// The single-pane view of every running sentinel. Polls the core so a project
// shows up here the moment its environment starts, with a live alert tally.
export default function Overview() {
  const [projects, setProjects] = useState([])
  const [reachable, setReachable] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    let alive = true
    const tick = () =>
      listProjects()
        .then((p) => alive && (setProjects(p), setReachable(true)))
        .catch(() => alive && setReachable(false))
    tick()
    const id = setInterval(tick, 2000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])

  const [loadingDemo, setLoadingDemo] = useState(false)
  const running = projects.filter((p) => p.running).length
  const totalAlerts = projects.reduce((n, p) => n + (p.alert_count || 0), 0)
  const existingDemo = projects.find((p) => p.is_demo)

  async function loadDemo() {
    if (existingDemo) {
      navigate(`/environments?p=${existingDemo.id}`)
      return
    }
    setLoadingDemo(true)
    try {
      const p = await createProject('demo', true)
      navigate(`/environments?p=${p.id}`)
    } finally {
      setLoadingDemo(false)
    }
  }

  return (
    <main className="max-w-[1440px] mx-auto px-gutter pt-24 pb-16">
      <div className="flex items-end justify-between mb-8">
        <div>
          <h1 className="font-headline-sm text-headline-sm font-bold">Sentinels</h1>
          <p className="text-on-surface-variant text-sm mt-1">
            {reachable ? `${running} running · ${totalAlerts} alerts` : 'core backend unreachable'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadDemo}
            disabled={loadingDemo}
            className="border border-primary text-primary font-label-caps text-label-caps rounded-lg px-4 py-2 disabled:opacity-50"
          >
            {loadingDemo ? 'Provisioning…' : existingDemo ? 'Open demo' : 'Load demo project'}
          </button>
          <button
            onClick={() => navigate('/environments')}
            className="bg-primary text-black font-label-caps text-label-caps rounded-lg px-4 py-2"
          >
            + New environment
          </button>
        </div>
      </div>

      {projects.length === 0 ? (
        <div className="h-[50vh] flex items-center justify-center text-on-surface-variant">
          No environments yet. Create one to start monitoring.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => navigate(`/environments?p=${p.id}`)}
              className="text-left bg-white/[0.03] border border-white/10 rounded-xl p-5 hover:border-primary transition-colors"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="font-medium truncate">{p.name}</span>
                <span className="flex items-center gap-1.5 text-xs">
                  <span className={`w-2 h-2 rounded-full ${p.running ? 'bg-green-400 animate-pulse' : 'bg-white/20'}`} />
                  {p.running ? 'running' : 'stopped'}
                </span>
              </div>
              <code className="text-xs text-on-surface-variant">id: {p.id}</code>
              <div className="flex items-center justify-between mt-4">
                <span className="text-xs text-on-surface-variant">
                  {p.monitoring ? 'model live' : 'monitor off'}
                </span>
                <span
                  className={`font-headline-sm text-headline-sm font-bold ${
                    p.alert_count ? 'text-red-400' : 'text-on-surface-variant'
                  }`}
                >
                  {p.alert_count || 0}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </main>
  )
}
