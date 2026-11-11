import { useEffect, useState } from 'react'
import { apiRequest } from '../api/client'
import MaintenancePage from '../pages/MaintenancePage'

export default function MaintenanceGate({ children }) {
  const [mode, setMode] = useState(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    const check = async () => {
      try {
        const status = await apiRequest('/status', { cache: 'no-store' })
        if (typeof status.maintenance_mode !== 'boolean') throw new Error('Invalid status')
        if (active) { setMode(status.maintenance_mode); setError(false) }
      } catch { if (active) setError(true) }
    }
    const maintenance = () => { if (active) setMode(true) }
    check()
    const timer = window.setInterval(check, 30_000)
    window.addEventListener('libria:maintenance', maintenance)
    return () => { active = false; window.clearInterval(timer); window.removeEventListener('libria:maintenance', maintenance) }
  }, [attempt])
  if (mode === true) return <MaintenancePage />
  if (mode === null) return <main className="auth-page"><div className="auth-card" role="status">
    <p>{error ? 'No pudimos conectar con LibrIAverse.' : 'Preparando tu universo literario…'}</p>
    {error && <button className="button" onClick={() => setAttempt(value => value + 1)}>Reintentar</button>}
  </div></main>
  return children
}
