import { createContext, useContext, useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { login as loginRequest, verifyToken } from './api'

// The dashboard is served by /cli's local status API (local_api.py), which
// mints one session token per `sentinal run` process and checks it against
// an admin password (--admin-password / $SENTINAL_ADMIN_PASSWORD, defaults
// to 'admin'). Single-operator, process-local — not the core backend's auth.

const TOKEN_KEY = 'sentinel_local_token'
const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    let cancelled = false
    if (!token) {
      setChecking(false)
      return
    }
    verifyToken(token).then((ok) => {
      if (cancelled) return
      if (!ok) {
        localStorage.removeItem(TOKEN_KEY)
        setToken(null)
      }
      setChecking(false)
    })
    return () => {
      cancelled = true
    }
    // Only re-verify when the token itself changes (e.g. after login/logout).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function login(password) {
    const newToken = await loginRequest(password)
    localStorage.setItem(TOKEN_KEY, newToken)
    setToken(newToken)
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
  }

  return (
    <AuthContext.Provider value={{ token, login, logout, checking }}>{children}</AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

export function RequireAuth({ children }) {
  const { token, checking } = useAuth()
  const location = useLocation()
  if (checking) {
    return null
  }
  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return children
}
