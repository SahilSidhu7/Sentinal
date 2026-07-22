import { useEffect, useState } from 'react'
import { getAttacks, respondToAttack, connectLiveFeed } from '../lib/api'
import { mockActivityTemplates } from '../lib/mockData'
import GlassPanel from '../components/GlassPanel'
import MaterialIcon from '../components/MaterialIcon'
import ProgressBar from '../components/ProgressBar'

const KIND_STYLE = {
  success: { iconBg: 'bg-primary/10', iconColor: 'text-primary', highlight: 'text-primary', icon: 'cloud_sync' },
  warning: { iconBg: 'bg-error/10', iconColor: 'text-error', highlight: 'text-error', icon: 'warning' },
  neutral: { iconBg: 'bg-surface-container-highest', iconColor: 'text-on-surface-variant', highlight: 'text-on-surface', icon: 'database' },
  auth: { iconBg: 'bg-primary/10', iconColor: 'text-primary', highlight: 'text-primary', icon: 'manage_accounts' },
}

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true }).toLowerCase()
}

function ActivityRow({ event, onRespond }) {
  const style = KIND_STYLE[event.kind] ?? KIND_STYLE.neutral
  const icon = event.kind === 'warning' && event.attack_type_guess === 'unrecognized_process' ? 'shield_question' : style.icon
  const meta = event.source_ip
    ? `IP: ${event.source_ip}`
    : event.region
      ? `Region: ${event.region}`
      : event.node
        ? `Node: ${event.node}`
        : event.image
          ? `Image: ${event.image}`
          : event.size
            ? `Size: ${event.size}`
            : ''

  return (
    <div className="animate-feed-entry flex items-center justify-between p-4 rounded-lg bg-white/2 border border-white/5 hover:border-white/10 transition-all">
      <div className="flex items-center gap-4">
        <div className={`w-10 h-10 rounded-lg ${style.iconBg} flex items-center justify-center`}>
          <MaterialIcon name={icon} className={`${style.iconColor} text-xl`} />
        </div>
        <div>
          <p className="text-on-surface font-body-md text-body-md">
            <span className={event.actor === 'System' ? 'text-on-surface-variant' : ''}>{event.actor}</span>{' '}
            <span className={`${style.highlight} font-medium`}>{event.message.replace(`${event.actor} `, '')}</span>
          </p>
          <p className="text-on-surface-variant font-body-sm text-body-sm flex items-center gap-2">
            <MaterialIcon name="schedule" className="text-xs" /> {formatTime(event.detected_at)}
            {meta && ` • ${meta}`}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {event.kind === 'warning' ? (
          <>
            <button
              className="px-4 py-1.5 rounded-lg bg-error text-on-error font-label-caps text-[10px] hover:opacity-90 transition-all"
              onClick={() => onRespond(event.id, 'block')}
            >
              BLOCK
            </button>
            <button
              className="px-3 py-1.5 rounded font-label-caps text-[10px] text-on-surface-variant border border-white/10 hover:bg-white/5"
              onClick={() => onRespond(event.id, 'allow')}
            >
              ALLOW
            </button>
          </>
        ) : event.kind === 'auth' || event.kind === 'success' ? (
          <>
            <button
              className="px-3 py-1.5 rounded font-label-caps text-[10px] text-on-surface-variant border border-white/10 hover:bg-white/5 transition-colors"
              onClick={() => onRespond(event.id, 'block')}
            >
              BLOCK
            </button>
            <button
              className="px-3 py-1.5 rounded font-label-caps text-[10px] bg-primary text-on-primary hover:opacity-90 transition-opacity"
              onClick={() => onRespond(event.id, 'allow')}
            >
              ALLOW
            </button>
          </>
        ) : (
          <button
            className="px-3 py-1.5 rounded font-label-caps text-[10px] text-on-surface-variant border border-white/10 hover:bg-white/5"
            onClick={() => onRespond(event.id, 'dismiss')}
          >
            DISMISS
          </button>
        )}
      </div>
    </div>
  )
}

export default function Activity() {
  const [events, setEvents] = useState([])

  useEffect(() => {
    getAttacks().then(setEvents)
    const disconnect = connectLiveFeed((event) => setEvents((prev) => [event, ...prev].slice(0, 20)))
    return disconnect
  }, [])

  useEffect(() => {
    const interval = setInterval(() => {
      if (Math.random() <= 0.6) return
      const t = mockActivityTemplates[Math.floor(Math.random() * mockActivityTemplates.length)]
      setEvents((prev) =>
        [
          {
            id: `sim-${Date.now()}`,
            actor: t.actor,
            message: `${t.actor} ${t.message} on ${t.target}`,
            kind: t.kind,
            node: 'Global-Any',
            detected_at: new Date(0).toISOString(),
            _now: true,
          },
          ...prev,
        ].slice(0, 20),
      )
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  function handleRespond(id, action) {
    respondToAttack(id, action)
    setEvents((prev) => prev.filter((e) => e.id !== id))
  }

  return (
    <main className="flex-1 mt-16 px-container-padding-mobile md:px-container-padding-desktop py-8 max-w-[1440px] mx-auto w-full flex flex-col">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <h1 className="font-headline-md text-headline-md text-on-surface mb-1">Live Activity</h1>
          <p className="text-on-surface-variant font-body-sm text-body-sm flex items-center gap-2">
            <span className="inline-block w-2 h-2 bg-primary rounded-full animate-pulse" />
            Monitoring 12 global nodes in real-time
          </p>
        </div>
        <div className="flex gap-3">
          <GlassPanel className="px-4 py-2 rounded-lg flex items-center gap-3">
            <span className="font-label-caps text-label-caps text-on-surface-variant">STATUS:</span>
            <span className="font-label-caps text-label-caps text-primary">VIGILANT</span>
          </GlassPanel>
          <GlassPanel className="px-4 py-2 rounded-lg flex items-center gap-3">
            <span className="font-label-caps text-label-caps text-on-surface-variant">UPTIME:</span>
            <span className="font-label-caps text-label-caps text-on-surface">99.98%</span>
          </GlassPanel>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-gutter flex-1">
        <GlassPanel as="div" className="lg:col-span-8 flex flex-col rounded-xl overflow-hidden border border-zinc-800">
          <div className="p-6 border-b border-white/5 flex justify-between items-center bg-white/[0.01]">
            <h2 className="font-label-caps text-label-caps text-on-surface tracking-widest">REAL-TIME TRAFFIC FEED</h2>
            <div className="flex gap-2">
              <MaterialIcon name="filter_list" className="text-on-surface-variant text-sm cursor-pointer hover:text-on-surface" />
              <MaterialIcon name="more_vert" className="text-on-surface-variant text-sm cursor-pointer hover:text-on-surface" />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-6 space-y-4 max-h-[60vh]">
            {events.map((event) => (
              <ActivityRow key={event.id} event={event} onRespond={handleRespond} />
            ))}
          </div>
        </GlassPanel>

        <div className="lg:col-span-4 flex flex-col gap-gutter h-full">
          <GlassPanel className="flex-1 rounded-xl overflow-hidden border border-zinc-800 flex flex-col">
            <div className="p-5 border-b border-white/5 bg-white/[0.01]">
              <h3 className="font-label-caps text-label-caps text-on-surface">Global Origin Points</h3>
            </div>
            <div className="flex-1 relative bg-[#050505] min-h-[240px]">
              <div className="absolute bottom-4 left-4 flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-primary" />
                  <span className="font-label-caps text-[10px] text-on-surface">SECURE FEED</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-error animate-pulse" />
                  <span className="font-label-caps text-[10px] text-on-surface">BLOCKED ATTACK</span>
                </div>
              </div>
            </div>
          </GlassPanel>

          <GlassPanel className="rounded-xl p-6 border border-zinc-800">
            <h3 className="font-label-caps text-label-caps text-on-surface mb-6">Sentinel Metrics</h3>
            <div className="space-y-6">
              <div className="space-y-2">
                <div className="flex justify-between items-center font-label-caps text-[10px]">
                  <span className="text-on-surface-variant">THREAT MITIGATION</span>
                  <span className="text-primary">94%</span>
                </div>
                <ProgressBar pct={94} />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-center font-label-caps text-[10px]">
                  <span className="text-on-surface-variant">NETWORK LOAD</span>
                  <span className="text-on-surface">22%</span>
                </div>
                <ProgressBar pct={22} barClassName="bg-on-surface-variant" />
              </div>
            </div>
          </GlassPanel>
        </div>
      </div>
    </main>
  )
}
