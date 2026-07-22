import { useEffect, useState } from 'react'
import { getScore, getFindings } from '../lib/api'
import GlassPanel from '../components/GlassPanel'
import MaterialIcon from '../components/MaterialIcon'
import ProgressBar from '../components/ProgressBar'
import SeverityBadge from '../components/SeverityBadge'
import StatusDot from '../components/StatusDot'

const SEVERITY_DOT = { high: 'error', medium: 'amber', safe: 'primary' }

export default function Security() {
  const [score, setScore] = useState({ score: 0, issues_open: 0, metrics: [] })
  const [findings, setFindings] = useState([])

  useEffect(() => {
    getScore().then(setScore)
    getFindings().then(setFindings)
  }, [])

  return (
    <main className="pt-24 pb-12 px-gutter max-w-[1440px] mx-auto min-h-screen">
      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-gutter">
        <section className="lg:col-span-4 flex flex-col gap-component-gap">
          <GlassPanel className="p-8 rounded-xl flex flex-col items-center justify-center text-center">
            <span className="font-label-caps text-label-caps text-on-surface-variant mb-4">GLOBAL SECURITY POSTURE</span>
            <h1
              className="font-headline-lg text-[120px] font-extrabold text-white leading-none mb-4"
              style={{ textShadow: '0 0 30px rgba(78, 222, 163, 0.2)' }}
            >
              {score.score}
            </h1>
            {score.issues_open > 0 && (
              <div className="flex items-center gap-2 px-4 py-2 bg-error-container/20 rounded-full border border-error/20">
                <StatusDot variant="error" pulse size="sm" />
                <p className="font-body-sm text-error font-medium">{score.issues_open} issues need attention</p>
              </div>
            )}
          </GlassPanel>

          <GlassPanel className="p-6 rounded-xl">
            <div className="flex justify-between items-center mb-6">
              <h3 className="font-headline-sm text-headline-sm">Active Monitoring</h3>
              <MaterialIcon name="analytics" className="text-primary" />
            </div>
            <div className="space-y-4">
              {score.metrics.map((m) => (
                <div key={m.key}>
                  <div className="flex justify-between items-end mb-2">
                    <span className="font-body-sm text-on-surface-variant">{m.label}</span>
                    <span className="font-label-caps text-label-caps text-primary">
                      {m.value}
                      {m.unit}
                    </span>
                  </div>
                  <ProgressBar pct={m.pct} height="h-1" barClassName={m.key === 'latency' ? 'bg-primary' : 'bg-on-surface'} />
                </div>
              ))}
            </div>
          </GlassPanel>
        </section>

        <section className="lg:col-span-8 flex flex-col gap-component-gap">
          <GlassPanel className="rounded-xl overflow-hidden">
            <div className="p-6 border-b border-white/5 flex justify-between items-center bg-white/[0.01]">
              <h2 className="font-headline-sm text-headline-sm">Security Issues</h2>
              <button className="font-label-caps text-label-caps text-on-surface-variant hover:text-primary transition-colors">
                MARK ALL AS READ
              </button>
            </div>
            <div className="divide-y divide-white/5">
              {findings.map((f) => (
                <div
                  key={f.id}
                  className="p-6 flex items-center justify-between group hover:bg-white/[0.02] transition-colors duration-200"
                >
                  <div className="flex items-center gap-6">
                    <StatusDot variant={SEVERITY_DOT[f.severity] ?? 'neutral'} size="lg" />
                    <div>
                      <h4 className="font-body-lg text-on-surface font-medium">{f.title}</h4>
                      <p className="font-body-sm text-on-surface-variant">{f.description}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <SeverityBadge severity={f.severity} />
                    <button className="p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <MaterialIcon name="chevron_right" className="text-on-surface-variant hover:text-white" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </GlassPanel>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-component-gap">
            <GlassPanel className="p-6 rounded-xl flex flex-col justify-between h-48 border-l-4 border-primary">
              <div>
                <span className="font-label-caps text-label-caps text-on-surface-variant">NETWORK TRAFFIC</span>
                <h5 className="font-headline-sm text-headline-sm mt-2">1.4 GB/s</h5>
              </div>
              <div className="flex gap-1 h-12 items-end">
                {[40, 60, 45, 80, 55, 100].map((h, i) => (
                  <div key={i} className={`flex-1 ${i === 5 ? 'bg-primary' : 'bg-primary/40'} rounded-t-sm`} style={{ height: `${h}%` }} />
                ))}
              </div>
            </GlassPanel>

            <GlassPanel className="p-6 rounded-xl flex flex-col justify-between h-48 overflow-hidden relative">
              <div className="relative z-10">
                <span className="font-label-caps text-label-caps text-on-surface-variant">ACTIVE THREATS</span>
                <h5 className="font-headline-sm text-headline-sm mt-2">ZERO</h5>
              </div>
              <div className="absolute right-0 bottom-0 opacity-10 scale-150">
                <MaterialIcon name="shield_lock" className="text-[120px]" />
              </div>
              <button className="relative z-10 self-start text-primary font-label-caps text-label-caps hover:underline mt-4">
                VIEW REPORT
              </button>
            </GlassPanel>
          </div>
        </section>
      </div>

      <footer className="mt-12 py-12 px-gutter border-t border-white/5 -mx-gutter">
        <div className="max-w-[1440px] mx-auto flex flex-col md:flex-row justify-between items-center gap-8">
          <div className="flex flex-col gap-2">
            <span className="font-headline-sm text-headline-sm font-bold tracking-tighter text-white">SENTINEL</span>
            <p className="font-body-sm text-on-surface-variant max-w-xs">
              Autonomous security orchestration for enterprise-level container environments.
            </p>
          </div>
          <div className="flex gap-12 font-label-caps text-label-caps text-on-surface-variant">
            <a className="hover:text-primary transition-colors" href="#">Documentation</a>
            <a className="hover:text-primary transition-colors" href="#">API Status</a>
            <a className="hover:text-primary transition-colors" href="#">Legal</a>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="font-body-sm text-on-surface font-medium">Operator 092</p>
              <p className="font-label-caps text-[10px] text-on-surface-variant">VERIFIED SESSION</p>
            </div>
            <div className="w-10 h-10 rounded-full border border-primary/40 bg-surface-container-high" />
          </div>
        </div>
      </footer>
    </main>
  )
}
