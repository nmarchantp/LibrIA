import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Eye, LockKeyhole, Globe, UserRoundPlus, UserRoundCheck } from 'lucide-react'
import { apiRequest } from '../api/client'
import ProfileShowcase from '../components/ProfileShowcase'
import ProfileHeader from '../components/ProfileHeader'
import ProfileAboutSection from '../components/ProfileAboutSection'
import ProfileFavoriteQuotes from '../components/ProfileFavoriteQuotes'
import useLiteraryPreferences from '../hooks/useLiteraryPreferences'
import './ProfilePage.css'
import './ProfilePanorama.css'

export default function CommunityProfilePage() {
  const { profileId } = useParams()
  const [params] = useSearchParams()
  const preview = params.get('preview') === '1'
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const { data, loading, error, retry } = useLiteraryPreferences(profileId, preview)
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
  return <div className="profile-page page-width reader-profile reader-profile--panoramic reader-community-profile">
    <div className="reader-profile-top">
    <ProfileHeader key={data.id} user={data} publicView panoramic />
    <div className="profile-social-actions"><span>{data.profile_visibility === 'private' ? <><LockKeyhole size={17} /> Perfil privado</> : <><Globe size={17} /> Perfil público</>}</span>
      {!data.is_owner && <button type="button" className="button primary" disabled={busy} aria-pressed={data.following} onClick={toggleFollow}>{data.following ? <UserRoundCheck size={18} /> : <UserRoundPlus size={18} />}{data.following ? 'Dejar de seguir' : 'Seguir'}</button>}
      {data.follows_you && !data.is_owner && <span>Te sigue</span>}
    </div>
    {data.can_view && <nav className="profile-tabs reader-profile-tabs" aria-label="Secciones del perfil"><button type="button" className="active" aria-pressed="true">Sobre mí</button></nav>}
    </div>
    {preview && <aside className="reader-personal-card profile-preview-banner" aria-label="Vista previa del perfil"><p><Eye size={18} aria-hidden="true" /> Así ve tu perfil un usuario que no sigues.</p><Link className="button" to="/profile">Volver a mi perfil</Link></aside>}
    <div className="reader-profile-main">
    {message && <p role="alert">{message}</p>}
    {params.get('follow') === '1' && !data.is_owner && !data.following && <p className="reader-personal-card">Llegaste a través de un perfil compartido. Pulsa «Seguir» para conectar con {data.display_name}.</p>}
    {!data.can_view ? <section className="reader-personal-card profile-locked"><LockKeyhole size={32} aria-hidden="true" /><h2>Este perfil es privado</h2><p>Esta persona debe seguirte para que puedas ver este perfil.</p><p>{data.following ? 'Ya sigues a esta persona. Podrás ver su perfil cuando te siga.' : 'Síguela para que reciba una notificación y pueda seguirte.'}</p></section> : <>

        {data.visible_sections.some(section => ['biography', 'genres', 'tropes', 'intensities', 'interests'].includes(section)) && <ProfileAboutSection preferences={data} publicOnly />}
        {data.visible_sections.includes('favorite_quotes') && <ProfileFavoriteQuotes publicView quotes={data.favorite_quotes} />}
        {!data.visible_sections.length && <p className="reader-personal-card">Esta persona aún no comparte secciones de su perfil.</p>}
        <ProfileShowcase profileId={profileId} sections={data.visible_sections} preview={preview} />
    </>}
  </div></div>
}
