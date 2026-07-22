import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import MaterialIcon from '../components/MaterialIcon'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [status, setStatus] = useState('idle') // idle | pending | success

  async function handleSubmit(e) {
    e.preventDefault()
    setStatus('pending')
    await login(username, password)
    setStatus('success')
    setTimeout(() => {
      navigate(location.state?.from?.pathname ?? '/activity', { replace: true })
    }, 800)
  }

  return (
    <div className="font-body-md text-on-background flex items-center justify-center min-h-screen relative">
      <main className="relative z-10 w-full max-w-md px-6 animate-entrance opacity-0">
        <div className="text-center mb-10">
          <h1 className="font-headline-sm text-headline-sm font-bold tracking-tighter text-on-surface mb-2">
            SENTINEL
          </h1>
          <p className="font-label-caps text-label-caps text-on-surface-variant tracking-[0.2em]">
            VIGILANCE SYSTEM ACCESS
          </p>
        </div>

        <div className="glass-panel rounded-lg p-8 md:p-10">
          <form className="space-y-6" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <label className="block font-label-caps text-label-caps text-on-surface-variant" htmlFor="username">
                OPERATOR ID
              </label>
              <div className="relative">
                <MaterialIcon
                  name="account_circle"
                  className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant text-[20px]"
                />
                <input
                  className="w-full bg-black border border-zinc-800 rounded-lg py-3.5 pl-12 pr-4 text-on-surface font-body-md placeholder:text-zinc-600 transition-all duration-200 focus:border-primary focus:shadow-[0_0_0_1px_#4edea3] focus:outline-none"
                  id="username"
                  name="username"
                  placeholder="Enter Username"
                  required
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="block font-label-caps text-label-caps text-on-surface-variant" htmlFor="password">
                SECURITY KEY
              </label>
              <div className="relative">
                <MaterialIcon
                  name="shield"
                  className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant text-[20px]"
                />
                <input
                  className="w-full bg-black border border-zinc-800 rounded-lg py-3.5 pl-12 pr-4 text-on-surface font-body-md placeholder:text-zinc-600 transition-all duration-200 focus:border-primary focus:shadow-[0_0_0_1px_#4edea3] focus:outline-none"
                  id="password"
                  name="password"
                  placeholder="••••••••"
                  required
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            <button
              className="w-full bg-primary text-on-primary font-bold py-4 rounded-lg flex items-center justify-center gap-2 hover:brightness-110 active:scale-[0.98] transition-all duration-200 disabled:pointer-events-none disabled:opacity-80"
              type="submit"
              disabled={status !== 'idle'}
            >
              {status === 'idle' && (
                <>
                  <span className="font-label-caps text-label-caps text-[14px]">Sign In</span>
                  <MaterialIcon name="arrow_forward" className="text-[18px]" />
                </>
              )}
              {status === 'pending' && <MaterialIcon name="refresh" className="animate-spin" />}
              {status === 'success' && <MaterialIcon name="check_circle" />}
            </button>
          </form>

          <div className="mt-8 text-center">
            <a
              className="font-label-caps text-label-caps text-zinc-500 hover:text-primary transition-colors duration-200"
              href="#"
            >
              FORGOT CREDENTIALS?
            </a>
          </div>
        </div>

        <div className="mt-12 flex items-center justify-center gap-4 opacity-50">
          <div className="h-[1px] flex-1 bg-zinc-800" />
          <div className="flex items-center gap-2 font-label-caps text-[10px] text-zinc-500">
            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
            ENCRYPTION ACTIVE: AES-256
          </div>
          <div className="h-[1px] flex-1 bg-zinc-800" />
        </div>
      </main>

      <div className="fixed bottom-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-primary/5 blur-[120px] rounded-full pointer-events-none" />
    </div>
  )
}
