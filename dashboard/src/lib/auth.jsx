import { createContext, useContext, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

// /dashboard has no backend session infra (docs/SPEC.md's /dashboard scope
// is intentionally no-auth, single-operator-on-the-box). This login is a
// fully local, client-side gate — no network call — matching the exported
// prototype's simulated-delay behavior exactly.

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('sentinel_local_token'))

  function login(username) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const newToken = `local-${username}`
        localStorage.setItem('sentinel_local_token', newToken)
        setToken(newToken)
        resolve()
      }, 1500)
    })
  }

  function logout() {
    localStorage.removeItem('sentinel_local_token')
    setToken(null)
  }

  return <AuthContext.Provider value={{ token, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}

export function RequireAuth({ children }) {
  const { token } = useAuth()
  const location = useLocation()
  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return children
}
