import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { LockKeyhole, Globe, UserRoundPlus, UserRoundCheck } from 'lucide-react'
import { apiRequest } from '../api/client'
import ProfileEvents from '../components/ProfileEvents'
import ProfileHeader from '../components/ProfileHeader'
import ProfileAboutSection from '../components/ProfileAboutSection'
import ProfileFavoriteQuotes from '../components/ProfileFavoriteQuotes'
import useLiteraryPreferences from '../hooks/useLiteraryPreferences'
import './ProfilePage.css'

export default function CommunityProfilePage() {
  const { profileId } = useParams()
  const [params, setParams] = useSearchParams()
  const [access, setAccess] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const { data, loading, error, retry } = useLiteraryPreferences(profileId)
  useEffect(() => {
    const controller = new AbortController()
    setAccess(null); setMessage('')
    apiRequest(`/profiles/${profileId}/events/access`, { headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` }, signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) setAccess({ ...result, profileId }) }).catch(() => {})
    return () => controller.abort()
  }, [profileId, data])
  async function toggleFollow() {
    setBusy(true); setMessage('')
    try {
      await apiRequest(`/profiles/${profileId}/follow`, { method: data.following ? 'DELETE' : 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` } })
      retry()
    } catch { setMessage('No se pudo actualizar el seguimiento. Intenta nuevamente.') }
    finally { setBusy(false) }
  }
  if (loading) return <div className="page-width page" role="status">Cargando perfil comunitario…</div>
  if (error) return <div className="page-width page"><p role="alert">{error}</p><button className="button primary" onClick={retry}>Reintentar</button></div>
  const eventsAllowed = data.can_view && access?.profileId === profileId && access.allowed
  const events = eventsAllowed && params.get('tab') === 'events'
  return <div className="profile-page page-width reader-profile reader-community-profile"><div className="reader-profile-main">
    <ProfileHeader key={data.id} user={data} publicView />
    <div className="profile-social-actions"><span>{data.profile_visibility === 'private' ? <><LockKeyhole size={17} /> Perfil privado</> : <><Globe size={17} /> Perfil público</>}</span>
      {data.is_owner ? <Link className="button" to="/settings?section=privacy">Configurar privacidad</Link> : <button type="button" className="button primary" disabled={busy} aria-pressed={data.following} onClick={toggleFollow}>{data.following ? <UserRoundCheck size={18} /> : <UserRoundPlus size={18} />}{data.following ? 'Dejar de seguir' : 'Seguir'}</button>}
      {data.follows_you && !data.is_owner && <span>Te sigue</span>}
    </div>
    {message && <p role="alert">{message}</p>}
    {params.get('follow') === '1' && !data.is_owner && !data.following && <p className="reader-personal-card">Llegaste a través de un perfil compartido. Pulsa «Seguir» para conectar con {data.display_name}.</p>}
    {!data.can_view ? <section className="reader-personal-card profile-locked"><LockKeyhole size={32} aria-hidden="true" /><h2>Este perfil es privado</h2><p>Esta persona debe seguirte para que puedas ver este perfil.</p><p>{data.following ? 'Ya sigues a esta persona. Podrás ver su perfil cuando te siga.' : 'Síguela para que reciba una notificación y pueda seguirte.'}</p></section> : <>
      {eventsAllowed && <nav className="profile-tabs reader-profile-tabs" aria-label="Secciones del perfil">{[['about', 'Sobre mí'], ['events', 'Eventos']].map(([value, label]) => <button key={value} className={events === (value === 'events') ? 'active' : ''} aria-pressed={events === (value === 'events')} onClick={() => setParams({ tab: value })}>{label}</button>)}</nav>}
      {events ? <ProfileEvents profileId={profileId} /> : <>
        {data.visible_sections.some(section => ['biography', 'genres', 'tropes', 'intensities'].includes(section)) && <ProfileAboutSection preferences={data} publicOnly />}
        {data.visible_sections.includes('interests') && <section className="reader-personal-card"><h2>Intereses</h2>{data.interests.length ? <ul>{data.interests.map(item => <li key={item.id}>{item.name}</li>)}</ul> : <p>Sin intereses publicados.</p>}</section>}
        {data.visible_sections.includes('favorite_quotes') && <ProfileFavoriteQuotes publicView quotes={data.favorite_quotes} />}
        {!data.visible_sections.length && <p className="reader-personal-card">Esta persona aún no comparte secciones de su perfil.</p>}
      </>}
    </>}
  </div></div>
}
