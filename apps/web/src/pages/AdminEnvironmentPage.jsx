import { useEffect, useState } from 'react'
import { apiRequest } from '../api/client'
import { environmentHelp } from './environmentHelp'
import './AdminEnvironmentPage.css'

function EnvironmentForm({ target }) {
  const [data, setData] = useState(null)
  const [draft, setDraft] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [search, setSearch] = useState('')
  const [reload, setReload] = useState(0)
  const dirty = Object.keys(draft).length > 0
  const request = (options = {}) => apiRequest(`/admin/environment/${target}`, {
    ...options, headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` },
  })
  useEffect(() => {
    const controller = new AbortController()
    apiRequest(`/admin/environment/${target}`, { signal: controller.signal,
      headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` },
    }).then(setData).catch(cause => { if (cause.name !== 'AbortError') setError(cause.message) })
    return () => controller.abort()
  }, [target, reload])
  useEffect(() => {
    if (!dirty) return
    const warn = event => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  async function save(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('')
    try {
      const result = await request({ method: 'PATCH', body: JSON.stringify({ revision: data.revision, values: draft }) })
      setData(result); setDraft({})
      setMessage(target === 'backend'
        ? 'Configuración guardada. Reinicia el backend y los procesos de trabajo para aplicar los cambios.'
        : 'Configuración guardada. Reinicia Vite en desarrollo; en producción reconstruye y publica la web.')
    } catch (cause) { setError(cause.message) }
    finally { setBusy(false) }
  }
  return <form className="environment-panel" onSubmit={save}>
    <h2>{target === 'backend' ? 'Backend' : 'Web'}</h2>
    <p>{target === 'backend' ? 'Archivo apps/backend/.env. Los valores guardados se aplican al reiniciar los servicios. Las variables definidas por el servidor tienen prioridad.' : 'Archivo apps/web/.env. Las variables VITE se incluyen en la web publicada y son públicas.'}</p>
    {error && <p role="alert">{error}</p>}
    {message && <p role="status">{message}</p>}
    {!data ? <><p>Cargando configuración…</p><button type="button" onClick={() => { setError(''); setReload(value => value + 1) }}>Reintentar</button></> : <>
      <label>Filtrar variables<input type="search" value={search} onChange={event => setSearch(event.target.value)} /></label>
      <fieldset disabled={busy}>
        {data.fields.filter(field => `${field.key} ${environmentHelp[field.key] || ''}`.toLowerCase().includes(search.toLowerCase())).map(field => <label className="environment-field" key={field.key}>
          <span>{field.key}</span>
          <small id={`help-${target}-${field.key}`}>{environmentHelp[field.key] || 'Variable de configuración de la aplicación.'}</small>
          <input type={field.secret ? 'password' : 'text'} autoComplete="off" maxLength={16000} aria-describedby={`help-${target}-${field.key}`}
            value={draft[field.key] ?? field.value ?? ''}
            placeholder={field.secret ? (field.configured ? 'Configurado · escribe para reemplazar' : 'Sin configurar') : 'Sin definir · se usa el valor predeterminado'}
            onChange={event => { const value = event.target.value; setDraft(current => ({ ...current, [field.key]: value })); setMessage('') }} />
          {field.secret && <small>El valor actual no se muestra. Solo se reemplaza si modificas este campo; vacío elimina su contenido.</small>}
        </label>)}
      </fieldset>
      <div className="environment-actions"><button className="button primary" disabled={busy || !dirty}>{busy ? 'Guardando…' : `Guardar ${Object.keys(draft).length || ''} cambios`}</button>
        <button type="button" disabled={busy || !dirty} onClick={() => { setDraft({}); setError('') }}>Descartar cambios</button>
        <button type="button" disabled={busy || dirty} onClick={() => { setError(''); setReload(value => value + 1) }}>Recargar archivo</button></div>
    </>}
  </form>
}

export default function AdminEnvironmentPage() {
  return <section className="environment-page"><h1>Configuración de la aplicación</h1>
    <p>Administración de las variables de backend y web. Disponible para todas las cuentas con permiso de administrador.</p>
    <p>Las claves y contraseñas actuales permanecen ocultas. Guardar modifica los archivos del servidor; no reinicia servicios automáticamente.</p>
    <EnvironmentForm target="backend" /><EnvironmentForm target="web" />
  </section>
}
