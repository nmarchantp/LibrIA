import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, LockKeyhole, UserRound, X } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { accountRequest } from '../services/accountService'
import AccountProfileSection from './AccountProfileSection'
import AccountSecuritySection from './AccountSecuritySection'
import ProfilePrivacySettings from './ProfilePrivacySettings'
import RoleManagementPanel from './RoleManagementPanel'
import { roleDetails, roleLabels } from './accountRoles'
import './AccountSettings.css'

const sections = [
  ['profile', 'Perfil público', 'Nombre, biografía y avatar', UserRound],
  ['privacy', 'Privacidad', 'Visibilidad en comunidad', Eye],
  ['security', 'Seguridad y acceso', 'Correo, clave y sesiones', LockKeyhole],
  ['role', 'Rol y permisos'],
]

// "Mi cuenta" tab: loads the account once and shows one section at a time (?section=).
export default function AccountSettings({ preferences }) {
  const { retry, endSession, session } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [account, setAccount] = useState(null)
  const [sessions, setSessions] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [attempt, setAttempt] = useState(0)
  const requested = params.get('section')
  const section = sections.some(([id]) => id === requested) ? requested : params.has('google_link') ? 'security' : 'profile'
  useEffect(() => {
    let active = true
    Promise.all([accountRequest('/me'), accountRequest('/me/sessions')]).then(([data, rows]) => {
      if (active) { setAccount(data); setSessions(rows); setError('') }
    }).catch(cause => { if (active) setError(cause.message) })
    return () => { active = false }
  }, [attempt])
  // redirect: path (or function of the result) to leave to after the session is closed.
  const run = async (operation, success, redirect) => {
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await operation()
      if (redirect) { endSession(); navigate(typeof redirect === 'function' ? redirect(result) : redirect); return result }
      setNotice(success); setAttempt(value => value + 1); retry()
      return result
    } catch (cause) { setError(cause.message) }
    finally { setBusy(false) }
  }
  const clear = () => { setError(''); setNotice('') }
  const role = account && (roleDetails[account.role] || roleDetails.lector)
  const RoleIcon = role?.icon

  let content
  if (!account) content = <section className="account-panel account-loading">
    {error ? <><p role="alert">{error}</p><button type="button" className="button account-button" onClick={() => setAttempt(value => value + 1)}>Reintentar</button></> : <p role="status">Cargando cuenta…</p>}
  </section>
  else if (section === 'privacy') content = <ProfilePrivacySettings preferences={preferences} />
  else if (section === 'security') content = <AccountSecuritySection account={account} sessions={sessions} currentSessionId={session?.session_id} busy={busy} run={run} />
  else if (section === 'role') content = <RoleManagementPanel key={account.id} user={account} />
  else content = <AccountProfileSection key={account.id} account={account} busy={busy} run={run} />

  return <div className="account-settings">
    <nav className="account-settings-nav" aria-label="Opciones de Mi cuenta">
      {sections.map(([id, title, hint, Icon]) => {
        const selected = section === id
        const NavIcon = id === 'role' ? RoleIcon || UserRound : Icon
        return <Link key={id} to={id === 'profile' ? '/settings' : `/settings?section=${id}`} className={selected ? 'selected' : ''} aria-current={selected ? 'page' : undefined} onClick={clear}>
          <span className="account-settings-nav-icon"><NavIcon size={17} aria-hidden="true" /></span>
          <span className="account-settings-nav-copy"><strong>{title}</strong><small>{id === 'role' ? role?.nav || 'Tipo de perfil' : hint}</small></span>
          {id === 'role' && account && <span className="account-role-tag">{account.role === 'admin' ? 'Admin' : roleLabels[account.role]}</span>}
        </Link>
      })}
    </nav>
    <div className="account-settings-content">
      {content}
      {account && (notice || error) && <div className={`account-toast ${error ? 'is-error' : 'is-success'}`} role={error ? 'alert' : 'status'}>
        <span>{error || notice}</span>
        <button type="button" aria-label="Cerrar mensaje" onClick={clear}><X size={16} aria-hidden="true" /></button>
      </div>}
    </div>
  </div>
}
