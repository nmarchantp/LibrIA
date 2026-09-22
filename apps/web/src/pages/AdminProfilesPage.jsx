import { useEffect, useState } from 'react'
import { apiRequest } from '../api/client'
import './AdminProfilesPage.css'

const PAGE_SIZE = 20
const roleLabels = { lector: 'Lector', influencer: 'Influencer', autor: 'Autor', libreria: 'Librería', admin: 'Administrador' }
const permissions = {
  lector: 'Reseñas, comentarios y avances de lectura.',
  influencer: 'Publicaciones, reseñas y comentarios.',
  autor: 'Publicaciones, eventos, reseñas y comentarios.',
  libreria: 'Publicaciones, promociones, eventos, reseñas y comentarios.',
  admin: 'Publicaciones, eventos, reseñas y administración de perfiles.',
}
const authHeaders = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })

export default function AdminProfilesPage() {
  const [tab, setTab] = useState('profiles')
  const [searchDraft, setSearchDraft] = useState('')
  const [query, setQuery] = useState('')
  const [role, setRole] = useState('')
  const [page, setPage] = useState(0)
  const [profiles, setProfiles] = useState([])
  const [total, setTotal] = useState(0)
  const [pending, setPending] = useState([])
  const [selected, setSelected] = useState(null)
  const [name, setName] = useState('')
  const [biography, setBiography] = useState('')
  const [reason, setReason] = useState('')
  const [requests, setRequests] = useState([])
  const [history, setHistory] = useState([])
  const [bookstore, setBookstore] = useState({ display_name: '', email: '', password: '' })
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const selectedId = selected?.id

  useEffect(() => {
    let active = true
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) })
    if (query) params.set('q', query)
    if (role) params.set('role', role)
    Promise.all([
      apiRequest(`/roles/profiles?${params}`, { headers: authHeaders() }),
      apiRequest('/roles/requests/pending', { headers: authHeaders() }),
    ]).then(([profilesData, pendingData]) => {
      if (!active) return
      setProfiles(profilesData.items)
      setTotal(profilesData.total)
      setPending(pendingData)
      setSelected(current => current ? profilesData.items.find(item => item.id === current.id) || current : null)
      setLoading(false)
      setError('')
    }).catch(() => {
      if (active) { setLoading(false); setError('No se pudieron cargar los perfiles. Inténtalo nuevamente.') }
    })
    return () => { active = false }
  }, [query, role, page, refreshKey])

  useEffect(() => {
    if (!selectedId) return
    let active = true
    Promise.all([
      apiRequest(`/roles/profiles/${selectedId}/requests`, { headers: authHeaders() }),
      apiRequest(`/roles/profiles/${selectedId}/history`, { headers: authHeaders() }),
    ]).then(([requestsData, historyData]) => {
      if (active) { setRequests(requestsData); setHistory(historyData) }
    }).catch(() => { if (active) setError('No se pudo cargar el historial del perfil.') })
    return () => { active = false }
  }, [selectedId, refreshKey])

  const mutate = async (path, method, body, success) => {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const result = await apiRequest(path, { method, headers: authHeaders(), body: JSON.stringify(body) })
      setNotice(success)
      setRefreshKey(current => current + 1)
      return result
    } catch (cause) {
      setError(cause.status === 409 ? 'La operación ya fue procesada o el correo está registrado.' : 'No se pudo guardar. Revisa los datos e inténtalo de nuevo.')
      return null
    } finally {
      setBusy(false)
    }
  }

  const openProfile = profile => {
    setSelected(profile)
    setName(profile.display_name)
    setBiography(profile.biography || '')
    setReason('')
    setRequests([])
    setHistory([])
    setError('')
    setNotice('')
  }
  const search = event => {
    event.preventDefault()
    setPage(0)
    setQuery(searchDraft.trim())
    setSelected(null)
  }
  const saveProfile = async event => {
    event.preventDefault()
    const result = await mutate(`/roles/profiles/${selected.id}`, 'PATCH',
      { display_name: name.trim(), biography: biography.trim() || null }, 'Datos del perfil actualizados.')
    if (result) setSelected(result)
  }
  const revoke = async event => {
    event.preventDefault()
    const result = await mutate(`/roles/profiles/${selected.id}/revoke`, 'POST',
      { reason: reason.trim() }, 'Permiso revocado. La cuenta vuelve a ser lectora.')
    if (result) { setSelected(result); setReason('') }
  }
  const decide = async (request, action) => {
    const result = await mutate(`/roles/requests/${request.id}/${action}`, 'POST', {},
      action === 'approve' ? 'Perfil verificado y habilitado para publicar.' : 'Solicitud rechazada.')
    if (result) setPending(current => current.filter(item => item.id !== request.id))
  }
  const createBookstore = async event => {
    event.preventDefault()
    const result = await mutate('/roles/bookstores', 'POST', bookstore, 'Librería creada. Ya puede iniciar sesión.')
    if (result) {
      setBookstore({ display_name: '', email: '', password: '' })
      setSearchDraft('')
      setQuery('')
      setRole('libreria')
      setPage(0)
      setTab('profiles')
      openProfile(result)
      setNotice('Librería creada. Ya puede iniciar sesión.')
    }
  }

  return <div className="admin-profiles page-width">
    <header className="admin-header"><span className="kicker">ADMINISTRACIÓN</span><h1>Mantenedor de perfiles</h1><p>Revisa las cuentas, verifica perfiles profesionales y crea librerías. Los permisos de publicación dependen del perfil vigente.</p></header>
    <nav className="admin-tabs" aria-label="Secciones del mantenedor">
      <button className={tab === 'profiles' ? 'active' : ''} onClick={() => setTab('profiles')}>Perfiles</button>
      <button className={tab === 'requests' ? 'active' : ''} onClick={() => setTab('requests')}>Solicitudes pendientes ({pending.length})</button>
      <button className={tab === 'bookstore' ? 'active' : ''} onClick={() => setTab('bookstore')}>Crear librería</button>
    </nav>
    {error && <p className="admin-message error" role="alert">{error}</p>}
    {notice && <p className="admin-message" role="status">{notice}</p>}

    {tab === 'profiles' && <>
      <form className="admin-filters" onSubmit={search}>
        <label>Buscar por nombre o correo<input value={searchDraft} onChange={event => setSearchDraft(event.target.value)} maxLength="100" placeholder="Nombre o correo" /></label>
        <label>Tipo de perfil<select value={role} onChange={event => { setRole(event.target.value); setPage(0); setSelected(null) }}><option value="">Todos</option>{Object.entries(roleLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        <button className="button primary" disabled={loading}>Buscar</button>
      </form>
      <p className="admin-count">{loading ? 'Cargando perfiles...' : `${total} perfiles encontrados`}</p>
      <div className="admin-layout">
        <section className="admin-list" aria-label="Perfiles">
          {!loading && profiles.length === 0 && <p className="admin-empty">No hay perfiles con esos filtros.</p>}
          {profiles.map(profile => <button type="button" key={profile.id} className={`admin-profile-row ${selected?.id === profile.id ? 'selected' : ''}`} onClick={() => openProfile(profile)}>
            <span className="admin-profile-initial">{profile.display_name.trim().charAt(0).toUpperCase()}</span>
            <span className="admin-profile-main"><strong>{profile.display_name}</strong><small>{profile.email}</small></span>
            <span className="admin-profile-meta"><span className={`user-role-badge role-${profile.role}`}>{roleLabels[profile.role]}</span>{profile.pending_role && <small>Solicita {roleLabels[profile.pending_role]}</small>}</span>
          </button>)}
          {total > PAGE_SIZE && <div className="admin-pagination"><button className="button" disabled={page === 0 || loading} onClick={() => { setPage(value => value - 1); setSelected(null) }}>Anterior</button><span>Página {page + 1} de {Math.ceil(total / PAGE_SIZE)}</span><button className="button" disabled={(page + 1) * PAGE_SIZE >= total || loading} onClick={() => { setPage(value => value + 1); setSelected(null) }}>Siguiente</button></div>}
        </section>
        {selected && <section className="admin-detail" aria-label={`Gestionar perfil de ${selected.display_name}`}>
          <div className="admin-detail-heading"><div><span className="kicker">PERFIL SELECCIONADO</span><h2>{selected.display_name}</h2><p>{selected.email}</p></div><button type="button" className="admin-close" onClick={() => setSelected(null)} aria-label="Cerrar detalle">×</button></div>
          <p className="admin-permissions"><strong>{roleLabels[selected.role]}</strong> · {permissions[selected.role]}</p>
          <form className="admin-form" onSubmit={saveProfile}>
            <h3>Datos públicos</h3>
            <label>Nombre visible<input value={name} onChange={event => setName(event.target.value)} minLength="2" maxLength="100" required /></label>
            <label>Biografía<textarea value={biography} onChange={event => setBiography(event.target.value)} maxLength="1000" rows="3" /></label>
            <button className="button primary" disabled={busy || !name.trim()}>Guardar cambios</button>
          </form>
          {selected.pending_role && <p className="admin-inline-note">Tiene una solicitud pendiente para ser {roleLabels[selected.pending_role]}. Revísala en “Solicitudes pendientes”.</p>}
          {(selected.role === 'autor' || selected.role === 'influencer') && <form className="admin-form admin-revoke" onSubmit={revoke}>
            <h3>Revocar permiso de publicación</h3><p>La cuenta volverá a ser lectora. Sus publicaciones anteriores seguirán visibles.</p>
            <label>Motivo<textarea value={reason} onChange={event => setReason(event.target.value)} minLength="10" maxLength="1000" rows="2" required /></label>
            <button className="button" disabled={busy || reason.trim().length < 10}>Revocar permiso</button>
          </form>}
          <div className="admin-history"><h3>Solicitudes de verificación</h3>{requests.length === 0 && <p>Sin solicitudes.</p>}{requests.map(request => <p key={request.id}><strong>{roleLabels[request.requested_role]}</strong> · {request.status === 'approved' ? 'Aprobada' : request.status === 'rejected' ? 'Rechazada' : 'Pendiente'} · {new Date(request.created_at).toLocaleDateString('es-CL')}<br />{request.note}</p>)}
            <h3>Revocaciones</h3>{history.length === 0 && <p>Sin revocaciones.</p>}{history.map(change => <p key={change.id}><strong>{roleLabels[change.previous_role]} → {roleLabels[change.new_role]}</strong> · {new Date(change.created_at).toLocaleDateString('es-CL')}<br />{change.reason}<br /><small>Por {change.admin_name}</small></p>)}</div>
        </section>}
      </div>
    </>}

    {tab === 'requests' && <section className="admin-requests"><h2>Solicitudes pendientes</h2>{pending.length === 0 && <p className="admin-empty">No hay solicitudes pendientes.</p>}{pending.map(request => <article className="admin-request" key={request.id}>
      <div><strong>{request.display_name}</strong><small>{request.email} · Solicita {roleLabels[request.requested_role]}</small></div>
      <p>{request.note}</p><div className="admin-request-actions"><button className="button primary" disabled={busy} onClick={() => decide(request, 'approve')}>Aprobar</button><button className="button" disabled={busy} onClick={() => decide(request, 'reject')}>Rechazar</button></div>
    </article>)}</section>}

    {tab === 'bookstore' && <section className="admin-bookstore"><h2>Crear librería</h2><p>Solo un administrador puede crear este tipo de cuenta. Entrega la contraseña inicial por un canal seguro.</p>
      <form className="admin-form" onSubmit={createBookstore}>
        <label>Nombre visible<input value={bookstore.display_name} onChange={event => setBookstore(current => ({ ...current, display_name: event.target.value }))} minLength="2" maxLength="100" required /></label>
        <label>Correo<input type="email" value={bookstore.email} onChange={event => setBookstore(current => ({ ...current, email: event.target.value }))} required /></label>
        <label>Contraseña inicial<input type="password" value={bookstore.password} onChange={event => setBookstore(current => ({ ...current, password: event.target.value }))} minLength="8" required /></label>
        <button className="button primary" disabled={busy}>Crear cuenta de librería</button>
      </form>
    </section>}
  </div>
}
