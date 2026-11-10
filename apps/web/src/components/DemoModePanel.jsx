import { useEffect, useRef, useState } from 'react'
import { apiRequest } from '../api/client'

export default function DemoModePanel() {
  const [status, setStatus] = useState(null)
  const [interval, setIntervalValue] = useState(30)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const initialized = useRef(false)
  const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })

  useEffect(() => {
    let active = true
    const load = () => apiRequest('/admin/demo', { headers: headers() })
      .then(data => { if (active) {
        setStatus(data); setError('')
        if (!initialized.current) { setIntervalValue(data.interval_seconds); initialized.current = true }
      } })
      .catch(cause => { if (active) setError(cause.message) })
    load()
    const timer = window.setInterval(load, 5000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])

  async function toggle() {
    setBusy(true); setError('')
    try {
      const data = await apiRequest('/admin/demo', { method: 'PATCH', headers: headers(),
        body: JSON.stringify({ enabled: !status.enabled, interval_seconds: Number(interval) }) })
      setStatus(data)
    } catch (cause) { setError(cause.message) }
    finally { setBusy(false) }
  }

  return <section className="environment-panel" aria-label="Modo demostración">
    <h2>Modo demostración</h2>
    <p>Una comunidad simulada con ocho perfiles identificados como demo. Prepara libros del catálogo,
      lecturas, reseñas, publicaciones, eventos y conversaciones sin cargar contenido a mano.</p>
    <p>Al activar autorizas importar una selección limitada de libros verificados si hace falta.
      La primera preparación es gradual y necesita acceso al proveedor cuando el catálogo está vacío.</p>
    {error && <p role="alert">{error}</p>}
    {status && <>
      <p role="status"><strong>{status.enabled ? 'Activado' : 'Desactivado'}</strong>
        {' · '}{status.sequence} pasos completados</p>
      {!!status.selected_books?.length && <p>Libros preparados con portada: {status.selected_books.join(', ')}.</p>}
      {!!status.missing_books?.length && <p>Pendientes de conseguir con portada: {status.missing_books.join(', ')}.</p>}
      <label>Segundos entre actividades después de la preparación inicial
        <input type="number" min="10" max="3600" value={status.enabled ? status.interval_seconds : interval} disabled={busy || status.enabled}
          onChange={event => setIntervalValue(event.target.value)} /></label>
      <button type="button" className="button primary" disabled={busy || !Number.isInteger(Number(interval)) || Number(interval) < 10 || Number(interval) > 3600}
        onClick={toggle}>{busy ? 'Guardando…' : status.enabled ? 'Desactivar modo demo' : 'Activar modo demo'}</button>
      {status.last_run_at && <p>Última actividad: {new Date(status.last_run_at).toLocaleString('es-CL')}</p>}
      {status.last_error && <p role="alert">{status.last_error} {status.enabled && 'Se reintentará automáticamente.'}</p>}
    </>}
    <p>El cambio se aplica sin reiniciar. Al desactivar, una operación en curso puede terminar;
      después se detiene la generación. El contenido creado se conserva y puedes retomarlo.</p>
  </section>
}
