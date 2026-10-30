import { useEffect, useState } from 'react'
import { accountRequest } from '../services/accountService'

export default function AdminAccountManagement({ onChanged }) {
  const [state, setState] = useState('')
  const [page, setPage] = useState(0)
  const [data, setData] = useState({ items: [], total: 0 })
  const [selected, setSelected] = useState(null)
  const [history, setHistory] = useState([])
  const [reason, setReason] = useState('')
  const [role, setRole] = useState('lector')
  const [username, setUsername] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    const params = new URLSearchParams({ limit: '20', offset: String(page * 20) })
    if (state) params.set('state', state)
    accountRequest(`/admin?${params}`).then(rows => { if (active) setData(rows) }).catch(cause => { if (active) setError(cause.message) })
    return () => { active = false }
  }, [state, page, attempt])
  useEffect(() => {
    if (!selected) return
    let active = true
    accountRequest(`/admin/${selected.id}/history`).then(rows => { if (active) setHistory(rows) }).catch(cause => { if (active) setError(cause.message) })
    return () => { active = false }
  }, [selected, attempt])
  const change = async (action, body, method = 'PATCH') => {
    setBusy(true); setError(''); setNotice('')
    try { const result = await accountRequest(`/admin/${selected.id}/${action}`, method, { ...body, ...(action === 'verification' ? { note: reason } : { reason }) }); if (result?.username) setSelected(result); setAttempt(v => v + 1); setNotice('Operación registrada.'); onChanged?.() }
    catch (cause) { setError(cause.message) }
    finally { setBusy(false) }
  }
  return <section className="admin-accounts"><h2>Estado, seguridad e historial de cuentas</h2>
    <label>Estado<select value={state} onChange={e => { setState(e.target.value); setPage(0); setSelected(null) }}><option value="">Todos</option><option value="active">Activas</option><option value="suspended">Suspendidas</option><option value="pending_deletion">Pendientes de eliminación</option><option value="anonymized">Anonimizadas</option></select></label>
    <div className="admin-profile-list">{data.items.map(item => <button className="button" key={item.id} onClick={() => { setSelected(item); setUsername(item.username); setRole(item.role); setReason(''); setHistory([]) }}>{item.display_name} · {item.username} · {item.account_status}{item.suspended ? ' · Suspendida' : ''}</button>)}</div>
    <p>{data.total} cuentas</p><button className="button" disabled={page === 0} onClick={() => setPage(v => v - 1)}>Anterior</button><button className="button" disabled={(page + 1) * 20 >= data.total} onClick={() => setPage(v => v + 1)}>Siguiente</button>
    {selected && <div><h3>{selected.username}</h3><label>Motivo obligatorio<textarea value={reason} onChange={e => setReason(e.target.value)} minLength={10} maxLength={1000} /></label><fieldset disabled={busy || reason.trim().length < 10 || selected.account_status === 'anonymized'}>
      <button className="button" onClick={() => change('suspension', { suspended: !selected.suspended })}>{selected.suspended ? 'Levantar suspensión' : 'Suspender cuenta'}</button>
      <label>Tipo exclusivo<select value={role} onChange={e => setRole(e.target.value)}>{['lector', 'autor', 'influencer', 'libreria', 'admin'].map(value => <option key={value} value={value}>{value}</option>)}</select></label>
      <button className="button" onClick={() => change('role', { role })}>Cambiar tipo con verificación aprobada</button>
      {['autor', 'influencer', 'libreria'].includes(role) && <button className="button" onClick={() => change('verification', { requested_role: role }, 'POST')}>Solicitar revisión profesional</button>}
      <label>Nombre de usuario excepcional<input value={username} onChange={e => setUsername(e.target.value)} pattern="[a-z0-9_]{3,64}" /></label><button className="button" onClick={() => change('username', { username })}>Autorizar cambio de nombre de usuario</button>
    </fieldset><h3>Historial administrativo (últimos 50 cambios)</h3>{history.map(item => <article key={item.id}><strong>{item.action}</strong> · {new Date(item.created_at).toLocaleString()}<p>{item.reason}</p><pre>{JSON.stringify({ antes: item.before, después: item.after }, null, 2)}</pre><small>Responsable: {item.actor_user_id || 'Proceso de sistema'} · Correlación: {item.correlation_id}</small></article>)}</div>}
    {notice && <p role="status">{notice}</p>}{error && <p role="alert">{error}</p>}
  </section>
}
