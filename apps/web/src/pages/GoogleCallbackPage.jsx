import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { consumeProfileDestination } from '../services/profileDestination'

export default function GoogleCallbackPage() {
  const { googleLogin } = useAuth()
  const navigate = useNavigate()
  const started = useRef(false)
  useEffect(() => {
    if (started.current) return
    started.current = true
    googleLogin().then(() => navigate(consumeProfileDestination(), { replace: true }))
      .catch(() => navigate('/login?google_error=failed', { replace: true }))
  }, [googleLogin, navigate])
  return <main className="auth-page"><p role="status">Iniciando sesión con Google…</p></main>
}
