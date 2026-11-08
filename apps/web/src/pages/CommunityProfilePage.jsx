import { useEffect, useState } from 'react'
import { BookOpen, CalendarDays } from 'lucide-react'
import { useParams, useSearchParams } from 'react-router-dom'
import { apiRequest } from '../api/client'
import ProfileEvents from '../components/ProfileEvents'
import ProfileHeader from '../components/ProfileHeader'
import ProfilePanels from '../components/ProfilePanels'
import ProfileAboutSection from '../components/ProfileAboutSection'
import useLiteraryPreferences from '../hooks/useLiteraryPreferences'
import './ProfilePage.css'

export default function CommunityProfilePage() {
  const { profileId } = useParams()
  const [params, setParams] = useSearchParams()
  const [access, setAccess] = useState(null)
  useEffect(() => {
    const controller = new AbortController()
    apiRequest(`/profiles/${profileId}/events/access`, { headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` }, signal: controller.signal }).then(result => setAccess({ ...result, profileId })).catch(() => setAccess(null))
    return () => controller.abort()
  }, [profileId])
  const allowed = access?.profileId === profileId && access.allowed
  const events = allowed && params.get('tab') === 'events'
  const { data, loading, error, retry } = useLiteraryPreferences(profileId)
  if (loading) return <div className="page-width page" role="status">Cargando perfil comunitario…</div>
  if (error) return <div className="page-width page"><p role="alert">{error}</p><button className="button primary" type="button" onClick={retry}>Reintentar</button></div>
  return <div className="profile-page page-width reader-profile reader-community-profile">
    <div className="reader-profile-main"><ProfileHeader key={data.id} user={data} publicView />{allowed && <nav className="profile-tabs reader-profile-tabs" aria-label="Secciones del perfil">{[['about', 'Sobre mí', BookOpen], ['events', 'Mis eventos', CalendarDays]].map(([value, label, Icon]) => <button key={value} aria-pressed={events === (value === 'events')} className={events === (value === 'events') ? 'active' : ''} onClick={() => setParams(current => { const next = new URLSearchParams(current); next.set('tab', value); return next })}><Icon size={18} />{label}</button>)}</nav>}<ProfilePanels key={profileId} active={events ? 'events' : 'about'} renderPanel={(value, active) => value === 'events' ? allowed && <ProfileEvents profileId={profileId} active={active} /> : <ProfileAboutSection preferences={data} publicOnly />} /></div>
  </div>
}
