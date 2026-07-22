import { useEffect, useState } from 'react'
import { getSettings, saveSettings } from '../lib/api'
import MaterialIcon from '../components/MaterialIcon'

const DEPARTMENTS = ['Cyber-Defense Intelligence', 'Physical Perimeter Response', 'System Infrastructure']

function Toggle({ checked, onChange }) {
  return (
    <label className="relative inline-flex items-center cursor-pointer">
      <input checked={checked} onChange={onChange} className="sr-only peer" type="checkbox" />
      <div className="w-11 h-6 bg-surface-container-highest rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-container" />
    </label>
  )
}

export default function Settings() {
  const [form, setForm] = useState(null)
  const [status, setStatus] = useState('idle') // idle | saving | done

  useEffect(() => {
    getSettings().then(setForm)
  }, [])

  function set(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setStatus('saving')
    await saveSettings(form)
    setStatus('done')
    setTimeout(() => setStatus('idle'), 2000)
  }

  if (!form) return null

  return (
    <main className="pt-24 pb-20 px-gutter max-w-[1000px] mx-auto min-h-screen custom-scrollbar">
      <header className="mb-12">
        <h1 className="font-headline-md text-headline-md text-on-surface mb-2">System Settings</h1>
        <p className="text-on-surface-variant font-body-md text-body-md">
          Manage your security perimeter, account details, and notification protocols.
        </p>
      </header>

      <form className="space-y-8" onSubmit={handleSubmit}>
        <section className="glass-panel p-6 rounded-xl">
          <div className="flex items-center gap-3 mb-6">
            <MaterialIcon name="person" className="text-primary" />
            <h2 className="font-headline-sm text-headline-sm text-on-surface">Account</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="font-label-caps text-label-caps text-on-surface-variant block">Operator Name</label>
              <input
                className="w-full bg-black border border-outline-variant px-4 py-3 rounded text-on-surface focus:border-primary focus:outline-none transition-colors"
                type="text"
                value={form.operator_name}
                onChange={(e) => set('operator_name', e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="font-label-caps text-label-caps text-on-surface-variant block">Email Address</label>
              <input
                className="w-full bg-black border border-outline-variant px-4 py-3 rounded text-on-surface focus:border-primary focus:outline-none transition-colors"
                type="email"
                value={form.email}
                onChange={(e) => set('email', e.target.value)}
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <label className="font-label-caps text-label-caps text-on-surface-variant block">Department</label>
              <select
                className="w-full bg-black border border-outline-variant px-4 py-3 rounded text-on-surface focus:border-primary focus:outline-none transition-colors appearance-none"
                value={form.department}
                onChange={(e) => set('department', e.target.value)}
              >
                {DEPARTMENTS.map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </div>
          </div>
        </section>

        <section className="glass-panel p-6 rounded-xl">
          <div className="flex items-center gap-3 mb-6">
            <MaterialIcon name="shield" className="text-primary" />
            <h2 className="font-headline-sm text-headline-sm text-on-surface">Security Preferences</h2>
          </div>
          <div className="space-y-6">
            <div className="flex justify-between items-center py-2">
              <div>
                <p className="font-body-md text-body-md text-on-surface">Two-Factor Authentication</p>
                <p className="text-on-surface-variant text-body-sm">Require hardware token for all system access.</p>
              </div>
              <Toggle checked={form.two_factor_enabled} onChange={(e) => set('two_factor_enabled', e.target.checked)} />
            </div>
            <div className="flex justify-between items-center py-2 border-t border-white/5">
              <div>
                <p className="font-body-md text-body-md text-on-surface">Automatic Session Timeout</p>
                <p className="text-on-surface-variant text-body-sm">Log out after 15 minutes of inactivity.</p>
              </div>
              <Toggle checked={form.session_timeout_enabled} onChange={(e) => set('session_timeout_enabled', e.target.checked)} />
            </div>
            <div className="space-y-2 pt-4">
              <label className="font-label-caps text-label-caps text-on-surface-variant block">IP Whitelist</label>
              <textarea
                className="w-full bg-black border border-outline-variant px-4 py-3 rounded text-on-surface focus:border-primary focus:outline-none transition-colors font-label-caps"
                placeholder="192.168.1.1, 10.0.0.1..."
                rows={3}
                value={form.ip_whitelist}
                onChange={(e) => set('ip_whitelist', e.target.value)}
              />
            </div>
          </div>
        </section>

        <section className="glass-panel p-6 rounded-xl">
          <div className="flex items-center gap-3 mb-6">
            <MaterialIcon name="notifications" className="text-primary" />
            <h2 className="font-headline-sm text-headline-sm text-on-surface">Notifications</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <label className="flex items-center gap-3 p-4 border border-outline-variant rounded hover:border-primary/50 transition-colors cursor-pointer bg-black/40">
              <input
                className="w-4 h-4 rounded text-primary-container bg-black border-outline-variant focus:ring-primary"
                type="checkbox"
                checked={form.notify_critical_alerts}
                onChange={(e) => set('notify_critical_alerts', e.target.checked)}
              />
              <span className="text-on-surface font-body-sm">Critical Alerts</span>
            </label>
            <label className="flex items-center gap-3 p-4 border border-outline-variant rounded hover:border-primary/50 transition-colors cursor-pointer bg-black/40">
              <input
                className="w-4 h-4 rounded text-primary-container bg-black border-outline-variant focus:ring-primary"
                type="checkbox"
                checked={form.notify_log_summaries}
                onChange={(e) => set('notify_log_summaries', e.target.checked)}
              />
              <span className="text-on-surface font-body-sm">Log Summaries</span>
            </label>
            <label className="flex items-center gap-3 p-4 border border-outline-variant rounded hover:border-primary/50 transition-colors cursor-pointer bg-black/40">
              <input
                className="w-4 h-4 rounded text-primary-container bg-black border-outline-variant focus:ring-primary"
                type="checkbox"
                checked={form.notify_marketing}
                onChange={(e) => set('notify_marketing', e.target.checked)}
              />
              <span className="text-on-surface font-body-sm">Marketing Info</span>
            </label>
          </div>
        </section>

        <div className="flex justify-end items-center pt-8 border-t border-white/10">
          <button
            className="px-6 py-3 text-on-surface-variant hover:text-on-surface transition-colors duration-200 font-label-caps text-label-caps mr-4"
            type="button"
          >
            Cancel
          </button>
          <button
            className="bg-primary-container text-on-primary-container px-12 py-3 rounded-lg font-bold font-label-caps text-label-caps hover:brightness-110 active:scale-95 transition-all shadow-[0_0_20px_rgba(16,185,129,0.2)] disabled:opacity-70"
            type="submit"
            disabled={status === 'saving'}
          >
            {status === 'idle' && 'Save Changes'}
            {status === 'saving' && 'Synchronizing...'}
            {status === 'done' && 'Complete'}
          </button>
        </div>
      </form>
    </main>
  )
}
