import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import Overview from './pages/Overview.jsx'
import Findings from './pages/Findings.jsx'
import Attacks from './pages/Attacks.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Overview />} />
          <Route path="findings" element={<Findings />} />
          <Route path="attacks" element={<Attacks />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
