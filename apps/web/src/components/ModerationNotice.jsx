import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import './Moderation.css'

export default function ModerationNotice() {
  const [message, setMessage] = useState('')
  useEffect(() => {
    const show = event => setMessage(event.detail)
    window.addEventListener('libria:moderation-pending', show)
    return () => window.removeEventListener('libria:moderation-pending', show)
  }, [])
  return message && <aside className="moderation-notice" role="status"><button type="button" aria-label="Cerrar aviso de moderación" onClick={() => setMessage('')}>×</button><p>{message}</p><Link to="/settings?tab=publications" onClick={() => setMessage('')}>Consultar estado privado</Link></aside>
}
