import { useEffect, useState } from 'react'
import './AdminAccountManagement.css'
import AdminUserPermissions from './AdminUserPermissions'
import { apiRequest } from '../api/client'
import { accountRequest } from '../services/accountService'

const roles = { lector: 'Lector', autor: 'Autor', influencer: 'Influencer', libreria: 'Librería', editorial: 'Editorial', admin: 'Administrador' }
const statuses = { active: 'Activa', suspended: 'Suspendida', pending_deletion: 'Eliminación pendiente', anonymized: 'Anonimizada' }

export default function AdminAccountManagement({ onChanged, mode = 'unified', openUserId }) {
  const [draft, setDraft] = useState('')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [state, setState] = useState('')
  const [page, setPage] = useState(0)
  const [data, setData] = useState({ items: [], total: 0 })
  const [selected, setSelected] = useState(null)
  const [history, setHistory] = useState([])
  const [reason, setReason] = useState('')
  const [name, setName] = useState('')
  const [biography, setBiography] = useState('')
  const [username, setUsername] = useState('')
  const [error, setError] = useState('')
  const [listError, setListError] = useState('')
  const [historyError, setHistoryError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    const params = new URLSearchParams({ limit: '20', offset: String(page * 20) })
    setLoading(true)
    setListError('')
    if (query) params.set('q', query)
    if (state) params.set('state', state)
    accountRequest(`/admin?${params}`).then(rows => { if (active) { setData(rows); setLoading(false) } }).catch(cause => { if (active) { setListError(cause.message); setLoading(false) } })
    return () => { active = false }
  }, [state, page, attempt, query])
  useEffect(() => {
    if (!selected) return
    let active = true
    setHistoryError('')
    accountRequest(`/admin/${selected.id}/history`).then(rows => { if (active) setHistory(rows) }).catch(cause => { if (active) setHistoryError(cause.message) })
    return () => { active = false }
  }, [selected, attempt])
  useEffect(() => {
    if (!openUserId) return
    let active = true
    accountRequest(`/admin/${openUserId.id}`).then(item => {
      if (!active) return
      setSelected(item); setName(item.display_name); setBiography(item.biography || ''); setUsername(item.username); setReason(''); setError(''); setNotice(''); setHistory([])
    }).catch(cause => { if (active) setListError(cause.message) })
    return () => { active = false }
  }, [openUserId])
  const change = async (action, body, method = 'PATCH') => {
    setBusy(true); setError(''); setNotice('')
    try { const result = await accountRequest(`/admin/${selected.id}/${action}`, method, { ...body, ...(action === 'verification' ? { note: reason } : { reason }) }); if (result?.username) setSelected(result); setAttempt(v => v + 1); setNotice(action === 'verification' ? 'Solicitud de verificación creada. Revísala en Solicitudes pendientes; el tipo de perfil aún no cambia.' : 'Operación registrada.'); onChanged?.() }
    catch (cause) { setError(cause.message) }
    finally { setBusy(false) }
  }
  return <section className="admin-accounts">
    <div className="accounts-heading"><div><h2>{mode !== 'accounts' ? 'Usuarios' : 'Cuentas y seguridad'}</h2><p>{mode !== 'accounts' ? 'Busca una vez y administra todos los datos, la seguridad, los permisos y las solicitudes del usuario.' : 'Administra el acceso, las suspensiones y el historial de las cuentas.'}</p></div><span className="accounts-total">{loading ? 'Cargando...' : `${data.total} cuentas`}</span></div>
    <form hidden={mode === 'unified' && Boolean(selected)} className="accounts-toolbar" onSubmit={event => { event.preventDefault(); setQuery(draft.trim()); setPage(0); setSelected(null); setAttempt(v => v + 1) }}>
      <label className="accounts-search">Buscar cuenta<input type="search" placeholder="Nombre, correo o usuario" value={draft} maxLength={100} onChange={event => setDraft(event.target.value)} /></label>
      <label>Estado<select value={state} onChange={e => { setState(e.target.value); setPage(0); setSelected(null) }}><option value="">Todos los estados</option><option value="active">Activas</option><option value="suspended">Suspendidas</option><option value="pending_deletion">Pendientes de eliminación</option><option value="anonymized">Anonimizadas</option></select></label>
      <button className="button primary" disabled={loading}>Buscar</button>
    </form>
    <div className={`accounts-workspace ${selected ? 'has-selection' : ''} ${mode === 'unified' ? 'unified-workspace' : ''}`}>
    <div className="accounts-directory" aria-busy={loading} hidden={mode === 'unified' && Boolean(selected)}>
      <div className="accounts-list-heading"><span>Cuenta</span><span>Perfil / Estado</span></div>
      <div className="admin-profile-list">
        {loading ? <p className="admin-empty" role="status">Cargando cuentas...</p> : listError ? <div className="admin-empty"><p role="alert">No se pudo cargar la lista. {listError}</p><button className="button" onClick={() => setAttempt(v => v + 1)}>Reintentar</button></div> : data.items.length === 0 ? <div className="admin-empty"><strong>No encontramos cuentas</strong><p>Prueba con otro nombre o cambia el filtro de estado.</p></div> : data.items.map(item => <button type="button" className={`account-row ${selected?.id === item.id ? 'selected' : ''}`} aria-pressed={selected?.id === item.id} key={item.id} onClick={() => { setSelected(item); setUsername(item.username); setName(item.display_name); setBiography(item.biography || ''); setReason(''); setHistory([]); setNotice(''); setError('') }}>
          <span className="admin-profile-initial">{(item.display_name || item.username).trim().charAt(0).toUpperCase()}</span>
          <span className="account-identity"><strong>{item.display_name || item.username}</strong><small title={item.email || item.username}>{item.email || `@${item.username}`}</small></span>
          <span className="account-badges"><span>{roles[item.role] || item.role}</span><span className={`account-status status-${item.suspended ? 'suspended' : item.account_status}`}>{statuses[item.suspended ? 'suspended' : item.account_status] || item.account_status}</span></span><span aria-hidden="true">&rsaquo;</span>
        </button>)}
      </div>
      <div className="admin-pagination"><span>{data.total ? `${page * 20 + 1} - ${Math.min((page + 1) * 20, data.total)} de ${data.total}` : '0 cuentas'}</span><div><button className="button" disabled={loading || page === 0} onClick={() => { setPage(v => v - 1); setSelected(null) }}>Anterior</button><button className="button" disabled={loading || (page + 1) * 20 >= data.total} onClick={() => { setPage(v => v + 1); setSelected(null) }}>Siguiente</button></div></div>
    </div>
    {selected && <section className="account-detail" aria-label={`Gestionar cuenta de ${selected.display_name}`}><div className="admin-detail-heading"><div><span className="kicker">CUENTA SELECCIONADA</span><h3>{selected.display_name}</h3></div><button type="button" className="admin-close" aria-label="Cerrar detalle de cuenta" onClick={() => setSelected(null)}>&times;</button></div><p className="account-handle">@{selected.username} ? {roles[selected.role]} ? {statuses[selected.suspended ? 'suspended' : selected.account_status]}</p>{mode === 'unified' && <button type="button" className="button" onClick={() => setSelected(null)}>Volver a los resultados</button>}<label>Motivo obligatorio<textarea value={reason} onChange={e => setReason(e.target.value)} minLength={10} maxLength={1000} rows={3} placeholder="Explica el motivo de la acción (mínimo 10 caracteres)" /><small className="account-help">Este motivo quedará registrado en el historial. {reason.trim().length}/10 caracteres mínimos.</small></label><fieldset disabled={busy || reason.trim().length < 10 || selected.account_status === 'anonymized'}>
      {mode !== 'users' && <><h3>Seguridad y acceso</h3><button className="button" onClick={() => change('suspension', { suspended: !selected.suspended })}>{selected.suspended ? 'Levantar suspensión' : 'Suspender cuenta'}</button></>}
      {mode !== 'accounts' && <><form className="admin-form" onSubmit={async event => {
        event.preventDefault(); setBusy(true); setError(''); setNotice('')
        try {
          const result = await apiRequest(`/roles/profiles/${selected.id}`, { method: 'PATCH', headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` }, body: JSON.stringify({ display_name: name.trim(), biography: biography.trim() || null, reason: reason.trim() }) })
          setSelected(current => ({ ...current, ...result })); setAttempt(v => v + 1); setNotice('Datos del usuario actualizados.'); onChanged?.()
        } catch (cause) { setError(cause.message) } finally { setBusy(false) }
      }}><h3>Datos del usuario</h3><label>Nombre visible<input value={name} onChange={event => setName(event.target.value)} minLength={2} maxLength={100} required /></label><label>Biografía<textarea value={biography} onChange={event => setBiography(event.target.value)} rows={3} /></label><small className="account-help">{Array.from(biography).length}/70 caracteres</small><label>Correo de acceso<input value={selected.email || ''} readOnly /></label><p className="account-help">El correo se cambia desde el proceso de verificación de Mi cuenta.</p><button className="button primary" disabled={name.trim().length < 2 || Array.from(biography).length > 70}>Guardar datos del usuario</button></form>
      <label>Nombre de usuario excepcional<input value={username} onChange={e => setUsername(e.target.value)} pattern="[a-z0-9_]{3,64}" /></label><button className="button" onClick={() => change('username', { username })}>Autorizar cambio de nombre de usuario</button></>}
    </fieldset>{mode === 'unified' && <AdminUserPermissions key={selected.id} user={selected} onChanged={result => { if (result) setSelected(current => ({ ...current, ...result })); setAttempt(v => v + 1); onChanged?.() }} />}{notice && <p className="admin-message" role="status">{notice}</p>}{error && <p className="admin-message error" role="alert">{error}</p>}<h3>Historial administrativo (últimos 50 cambios)</h3>{historyError && <p role="alert">No se pudo cargar el historial. {historyError}</p>}{history.map(item => <article key={item.id}><strong>{item.action}</strong> · {new Date(item.created_at).toLocaleString()}<p>{item.reason}</p><details><summary>Ver cambios registrados</summary><pre>{JSON.stringify({ antes: item.before, después: item.after }, null, 2)}</pre></details><small>Responsable: {item.actor_user_id || 'Proceso de sistema'} · Correlación: {item.correlation_id}</small></article>)}</section>}
    </div>
  </section>
}
