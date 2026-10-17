import { useEffect, useState } from 'react'
import { CheckCircle2, CircleAlert, LoaderCircle } from 'lucide-react'
import './ActionStatus.css'

function Working({ children }) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const started = Date.now()
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [])
  return <><LoaderCircle className="action-spinner" aria-hidden="true" /><div><strong>{children}</strong>
    <small>{seconds >= 10 ? `Sigue en proceso · ${seconds} s transcurridos. Puedes esperar en esta pantalla.` : 'En proceso…'}</small></div></>
}

export default function ActionStatus({ busy = false, message = '', error = '', floating = false }) {
  if (!busy && !message && !error) return null
  return <div className={`action-feedback ${busy ? 'working' : error ? 'failed' : 'completed'}${floating ? ' action-feedback-floating' : ''}`}
    role={error && !busy ? 'alert' : 'status'} aria-live={error && !busy ? 'assertive' : 'polite'} aria-atomic="true">
    {busy ? <Working>{message || 'Procesando solicitud…'}</Working> : <>
      {error ? <CircleAlert aria-hidden="true" /> : <CheckCircle2 aria-hidden="true" />}<span>{error || message}</span>
    </>}
  </div>
}
