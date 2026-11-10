import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, Users, UserRoundPlus, UserRoundCheck, ShieldCheck, Share2, Compass, Copy, Search } from 'lucide-react'
import { apiRequest, apiAssetUrl } from '../api/client'
import ProfileEditModal from './ProfileEditModal'
import ProfilePrivacySettings from './ProfilePrivacySettings'
import { useTheme } from '../context/ThemeContext'
import { createProfileQr } from '../services/profileQr'
import './ProfileSocialHub.css'

const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })

function PersonAvatar({ person }) {
  const [failed, setFailed] = useState(false)
  return <span className="profile-person-avatar">{person.avatar_url && !failed ? <img src={apiAssetUrl(person.avatar_url)} alt="" onError={() => setFailed(true)} /> : person.display_name.trim().slice(0, 1).toUpperCase()}</span>
}

function PeopleList({ kind, onFollowChange }) {
  const [offset, setOffset] = useState(0)
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [busy, setBusy] = useState(null)
  const [followed, setFollowed] = useState(new Set())
  const discover = kind === 'discover'
  useEffect(() => {
    const controller = new AbortController()
    setResult(null); setError('')
    const path = discover ? `/profiles/discover/people?offset=${offset}&q=${encodeURIComponent(search)}` : `/profiles/me/connections?kind=${kind}&offset=${offset}`
    apiRequest(path, { headers: headers(), signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setResult(data) })
      .catch(() => { if (!controller.signal.aborted) setError('No se pudo cargar la lista. Intenta nuevamente.') })
    return () => controller.abort()
  }, [discover, kind, offset, search, attempt])
  async function toggle(person) {
    setBusy(person.id); setError('')
    const isFollowing = followed.has(person.id)
    try {
      await apiRequest(`/profiles/${person.id}/follow`, { method: isFollowing ? 'DELETE' : 'POST', headers: headers() })
      setFollowed(previous => { const next = new Set(previous); if (isFollowing) next.delete(person.id); else next.add(person.id); return next })
      onFollowChange()
    } catch { setError('No se pudo actualizar el seguimiento. Intenta nuevamente.') }
    finally { setBusy(null) }
  }
  return <div className="profile-people-content">
    {discover && <div className="profile-people-search"><Search size={18} aria-hidden="true" /><input type="search" aria-label="Buscar personas por nombre" placeholder="Busca una nueva historia…" value={query} maxLength={100} onChange={event => { const value = event.target.value; setQuery(value); setSearch(value); setOffset(0) }} /></div>}
    {error && <div role="alert"><p>{error}</p><button type="button" className="button" onClick={() => setAttempt(value => value + 1)}>Reintentar</button></div>}
    {!result && !error && <p role="status">Buscando lectores…</p>}
    {result && <>{!result.items.length && <div className="profile-people-empty"><Users size={32} aria-hidden="true" /><p>{discover ? 'No encontramos más personas. Prueba con otro nombre.' : kind === 'followers' ? 'Cuando alguien te siga, aparecerá aquí.' : 'Las personas que sigas aparecerán aquí. Descubre nuevas historias y conecta con otros lectores.'}</p></div>}
      <ul className={discover ? 'profile-people-grid' : 'profile-people-list'}>{result.items.map(person => <li key={person.id} className="profile-person-card"><Link className="profile-person-link" to={`/profiles/${person.id}`}><PersonAvatar person={person} /><span>{person.display_name}</span></Link>{discover && <button type="button" className={`profile-person-follow${followed.has(person.id) ? ' is-following' : ''}`} disabled={busy !== null} aria-pressed={followed.has(person.id)} onClick={() => toggle(person)}>{followed.has(person.id) ? <UserRoundCheck size={17} /> : <UserRoundPlus size={17} />}{busy === person.id ? 'Actualizando…' : followed.has(person.id) ? 'Siguiendo' : 'Seguir'}</button>}</li>)}</ul>
      <div className="profile-people-pagination">{offset > 0 && <button type="button" className="button" onClick={() => setOffset(value => Math.max(0, value - (discover ? 12 : 30)))}>Anterior</button>}{result.has_more && <button type="button" className="button" onClick={() => setOffset(value => value + (discover ? 12 : 30))}>Siguiente</button>}</div>
    </>}
  </div>
}

function ShareProfile({ profileId, displayName }) {
  const { theme } = useTheme()
  const [image, setImage] = useState('')
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const url = profileId ? new URL(`/profiles/${encodeURIComponent(profileId)}?follow=1`, window.location.origin).href : ''
  useEffect(() => {
    let active = true
    if (!url) return
    setError(''); setImage('')
    createProfileQr(url, theme)
      .then(value => { if (active) setImage(value) }).catch(() => { if (active) setError('No se pudo generar el QR.') })
    return () => { active = false }
  }, [url, theme, attempt])
  async function copy() {
    try { await navigator.clipboard.writeText(url); setCopied(true) }
    catch { setError('No se pudo copiar. Puedes seleccionar y copiar el enlace de abajo.') }
  }
  return <div className="profile-share-content">
    <div className="profile-share-pass">
      <span className="profile-share-brand">LIBRIAVERSE · TU UNIVERSO LITERARIO</span>
      <div className="profile-share-qr">{image ? <img src={image} width="320" height="320" alt={`Código QR del perfil de ${displayName || 'usuario'}`} /> : error ? <button className="button" type="button" onClick={() => setAttempt(value => value + 1)}>Generar QR nuevamente</button> : <p role="status">Preparando tu código…</p>}</div>
      <div className="profile-share-name"><span aria-hidden="true" /><strong>{displayName || 'Mi perfil'}</strong><span aria-hidden="true" /></div>
    </div>
    <p>Una nueva conexión comienza con una historia. Escanea este código para visitar mi perfil y seguirme.</p>
    <label htmlFor="profile-share-url">Enlace a tu perfil</label><input id="profile-share-url" readOnly value={url} onFocus={event => event.target.select()} />
    <button className="button primary" type="button" onClick={copy} disabled={!url}><Copy size={17} />{copied ? 'Enlace copiado' : 'Copiar enlace'}</button>
    {copied && <span role="status">Enlace copiado al portapapeles.</span>}{error && <p role="alert">{error}</p>}
  </div>
}

export default function ProfileSocialHub({ preferences, displayName }) {
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [modal, setModal] = useState(null)
  useEffect(() => {
    const controller = new AbortController()
    apiRequest('/profiles/me/social-summary', { headers: headers(), signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) { setSummary(data); setError('') } })
      .catch(() => { if (!controller.signal.aborted) setError('No se pudieron cargar tus estadísticas.') })
    return () => controller.abort()
  }, [attempt])
  useEffect(() => {
    const refresh = () => setAttempt(value => value + 1)
    window.addEventListener('libria:book-activity-changed', refresh)
    return () => window.removeEventListener('libria:book-activity-changed', refresh)
  }, [])
  const details = {
    followers: { title: 'Seguidores', icon: Users, description: 'Personas que acompañan tu historia lectora.' },
    following: { title: 'Seguidos', icon: UserRoundCheck, description: 'Las historias con las que has elegido conectar.' },
    privacy: { title: 'Privacidad de mi perfil', icon: ShieldCheck, description: 'Tú decides qué partes de tu mundo compartes. Los cambios se guardan al instante.' },
    share: { title: 'Comparte tu historia', icon: BookOpen, description: 'Invita a otras personas a encontrarte en LibrIAverse.' },
    discover: { title: 'Descubrir personas', icon: Compass, description: 'Nuevas personas, nuevos mundos por descubrir.' },
  }
  const current = modal && details[modal]
  const Icon = current?.icon
  return <section className="profile-social-hub" aria-label="Tu comunidad lectora">
    <div className="profile-community-counters">
      <Link to="/profile?tab=library" className="profile-community-counter"><BookOpen size={18} aria-hidden="true" /><strong>{summary?.finished_books ?? '—'}</strong><span>Libros leídos</span></Link>
      <button type="button" className="profile-community-counter" aria-haspopup="dialog" onClick={() => setModal('followers')}><Users size={18} aria-hidden="true" /><strong>{summary?.followers ?? '—'}</strong><span>Seguidores</span></button>
      <button type="button" className="profile-community-counter" aria-haspopup="dialog" onClick={() => setModal('following')}><UserRoundCheck size={18} aria-hidden="true" /><strong>{summary?.following ?? '—'}</strong><span>Seguidos</span></button>
    </div>
    {error && <div className="profile-summary-error" role="alert">{error}<button type="button" onClick={() => setAttempt(value => value + 1)}>Reintentar</button></div>}
    <div className="profile-community-actions"><button type="button" aria-haspopup="dialog" onClick={() => setModal('privacy')}><ShieldCheck size={16} />Editar privacidad</button><button type="button" aria-haspopup="dialog" disabled={!summary?.profile_id && !preferences.data?.profile_id} onClick={() => setModal('share')}><Share2 size={16} />Compartir perfil</button><button type="button" aria-haspopup="dialog" onClick={() => setModal('discover')}><Compass size={16} />Descubrir personas</button></div>
    <ProfileEditModal open={Boolean(current)} title={current?.title} icon={Icon && <Icon />} description={current?.description} readOnly onClose={() => setModal(null)} onSubmit={event => event.preventDefault()} className={`profile-community-modal profile-community-modal-${modal}`}>
      {modal === 'privacy' ? <ProfilePrivacySettings preferences={preferences} /> : modal === 'share' ? <ShareProfile profileId={summary?.profile_id || preferences.data?.profile_id} displayName={displayName} /> : modal && <PeopleList key={modal} kind={modal} onFollowChange={() => setAttempt(value => value + 1)} />}
    </ProfileEditModal>
  </section>
}
