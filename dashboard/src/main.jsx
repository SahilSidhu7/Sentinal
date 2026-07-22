import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import { AuthProvider, RequireAuth } from './lib/auth'
import Login from './pages/Login.jsx'
import Activity from './pages/Activity.jsx'
import Security from './pages/Security.jsx'
import Containers from './pages/Containers.jsx'
import Settings from './pages/Settings.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <App />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="/activity" replace />} />
            <Route path="activity" element={<Activity />} />
            <Route path="security" element={<Security />} />
            <Route path="containers" element={<Containers />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
