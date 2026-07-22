import { useEffect, useState } from 'react'
import { mockContainers } from '../lib/mockData'
import GlassPanel from '../components/GlassPanel'
import MaterialIcon from '../components/MaterialIcon'
import StatusDot from '../components/StatusDot'

// Presentation-only: docs/SPEC.md has no containers table/endpoint (§5, §6
// only define findings/attack_events/bans/audit_log), so this screen has no
// real fetch path yet — it's mockContainers end to end.

const STATUS_BADGE = {
  running: 'bg-primary/10 text-primary',
  stopped: 'bg-white/5 text-on-surface-variant',
  error: 'bg-error/10 text-error',
}

const STATUS_DOT = {
  running: 'primary',
  stopped: 'neutral',
  error: 'error',
}

function ContainerCard({ container }) {
  const isRunning = container.status === 'running'
  const isStopped = container.status === 'stopped'
  return (
    <GlassPanel
      className={`p-6 rounded-xl transition-all duration-300 hover:border-primary/30 ${
        container.status === 'error' ? 'border-error/20' : ''
      }`}
    >
      <div className="flex justify-between items-start mb-6">
        <div className="flex items-center gap-3">
          <StatusDot variant={STATUS_DOT[container.status]} pulse={container.status !== 'stopped'} />
          <div>
            <h3 className="font-medium text-lg text-on-surface">{container.name}</h3>
            <p className="text-xs font-label-caps text-on-surface-variant">ID: {container.id}</p>
          </div>
        </div>
        <span className={`px-2 py-1 rounded text-[10px] font-bold font-label-caps ${STATUS_BADGE[container.status]}`}>
          {container.status.toUpperCase()}
        </span>
      </div>
      <div className="space-y-4 mb-6">
        <div className="flex justify-between text-sm">
          <span className="text-on-surface-variant">Image:</span>
          <span className="font-label-caps text-on-surface">{container.image}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-on-surface-variant">{isRunning ? 'Uptime:' : isStopped ? 'Status:' : 'Exit Code:'}</span>
          <span className={container.status === 'error' ? 'text-error font-bold' : 'text-on-surface'}>
            {container.uptime ?? container.exit_info}
          </span>
        </div>
        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
          <div
            className={`h-full ${container.status === 'error' ? 'bg-error' : isStopped ? 'bg-white/10' : 'bg-primary'}`}
            style={{ width: `${container.cpu_pct}%` }}
          />
        </div>
      </div>
      <div className="flex justify-between items-center pt-4 border-t border-white/5">
        <div className="flex gap-2">
          <button className="p-2 rounded-lg hover:bg-white/10 text-on-surface-variant hover:text-on-surface transition-colors" title="Logs">
            <MaterialIcon name="terminal" className="text-[20px]" />
          </button>
          <button className="p-2 rounded-lg hover:bg-white/10 text-on-surface-variant hover:text-on-surface transition-colors" title="Stats">
            <MaterialIcon name="monitoring" className="text-[20px]" />
          </button>
        </div>
        <div className="flex gap-1">
          <button
            className={`p-2 rounded-lg transition-colors ${
              isRunning ? 'text-on-surface-variant opacity-50 cursor-not-allowed' : 'hover:bg-primary/10 text-primary'
            }`}
          >
            <MaterialIcon name="play_arrow" filled className="text-[20px]" />
          </button>
          <button
            className={`p-2 rounded-lg transition-colors ${
              isRunning ? 'hover:bg-red-500/10 text-error' : 'text-on-surface-variant opacity-50 cursor-not-allowed'
            }`}
          >
            <MaterialIcon name="stop" filled className="text-[20px]" />
          </button>
          <button className="p-2 rounded-lg hover:bg-white/10 text-on-surface transition-colors">
            <MaterialIcon name="refresh" className="text-[20px]" />
          </button>
        </div>
      </div>
    </GlassPanel>
  )
}

export default function Containers() {
  const [containers, setContainers] = useState(mockContainers)

  useEffect(() => {
    const interval = setInterval(() => {
      setContainers((prev) =>
        prev.map((c) => {
          if (c.status === 'stopped') return c
          const variance = Math.floor(Math.random() * 6) - 3
          return { ...c, cpu_pct: Math.max(5, Math.min(100, c.cpu_pct + variance)) }
        }),
      )
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  const healthy = containers.filter((c) => c.status === 'running').length
  const errors = containers.filter((c) => c.status === 'error').length
  const avgCpu = Math.round(containers.reduce((sum, c) => sum + c.cpu_pct, 0) / containers.length)

  return (
    <main className="pt-24 pb-20 px-gutter max-w-[1440px] mx-auto">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end mb-12 gap-6">
        <div>
          <p className="font-label-caps text-label-caps text-primary mb-2">SYSTEM OVERVIEW</p>
          <h1 className="font-headline-lg text-headline-lg text-on-surface">Containers</h1>
        </div>
        <div className="flex gap-4">
          <button className="bg-primary text-on-primary px-6 py-2 rounded-lg flex items-center gap-2 font-medium transition-transform hover:scale-[1.02] active:scale-95">
            <MaterialIcon name="add" className="text-[20px]" />
            Deploy New
          </button>
          <button className="border border-white/20 text-on-surface px-6 py-2 rounded-lg flex items-center gap-2 font-medium hover:bg-white/5 transition-all">
            <MaterialIcon name="filter_list" className="text-[20px]" />
            Filter
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-12">
        <GlassPanel className="p-6 rounded-xl">
          <p className="text-on-surface-variant font-label-caps text-label-caps mb-1">TOTAL INSTANCES</p>
          <p className="font-headline-sm text-headline-sm text-on-surface">{containers.length}</p>
        </GlassPanel>
        <GlassPanel className="p-6 rounded-xl">
          <p className="text-on-surface-variant font-label-caps text-label-caps mb-1">HEALTHY</p>
          <p className="font-headline-sm text-headline-sm text-primary">{healthy}</p>
        </GlassPanel>
        <GlassPanel className="p-6 rounded-xl">
          <p className="text-on-surface-variant font-label-caps text-label-caps mb-1">ERRORS</p>
          <p className="font-headline-sm text-headline-sm text-error">{errors}</p>
        </GlassPanel>
        <GlassPanel className="p-6 rounded-xl">
          <p className="text-on-surface-variant font-label-caps text-label-caps mb-1">CPU LOAD</p>
          <p className="font-headline-sm text-headline-sm text-on-surface">{avgCpu}%</p>
        </GlassPanel>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {containers.map((c) => (
          <ContainerCard key={c.id} container={c} />
        ))}
        <div className="border-2 border-dashed border-white/10 rounded-xl flex flex-col items-center justify-center p-8 hover:border-primary/40 hover:bg-white/5 transition-all group cursor-pointer">
          <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mb-4 group-hover:bg-primary/20 transition-all">
            <MaterialIcon name="add" className="text-on-surface-variant group-hover:text-primary transition-all" />
          </div>
          <p className="font-medium text-on-surface-variant group-hover:text-on-surface transition-all">Deploy Container</p>
          <p className="text-xs text-on-surface-variant mt-2 text-center max-w-[200px]">
            Launch a new instance from your registry images.
          </p>
        </div>
      </div>

      <footer className="fixed bottom-0 w-full bg-surface-container-lowest/90 backdrop-blur-md border-t border-white/5 z-40">
        <div className="max-w-[1440px] mx-auto h-8 px-gutter flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <StatusDot variant="primary" />
              <span className="text-[10px] font-label-caps text-on-surface-variant uppercase">Sentinel Core Active</span>
            </div>
            <span className="text-[10px] font-label-caps text-white/20">|</span>
            <span className="text-[10px] font-label-caps text-on-surface-variant">NODE: US-EAST-01A</span>
          </div>
          <div className="flex items-center gap-4 text-[10px] font-label-caps text-on-surface-variant">
            <span>LATENCY: 12ms</span>
            <span>VER: 4.8.2-PRO</span>
          </div>
        </div>
      </footer>
    </main>
  )
}
