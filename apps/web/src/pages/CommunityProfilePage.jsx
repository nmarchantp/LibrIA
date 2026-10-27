import { useParams } from 'react-router-dom'
import ProfileHeader from '../components/ProfileHeader'
import ProfileAboutSection from '../components/ProfileAboutSection'
import useLiteraryPreferences from '../hooks/useLiteraryPreferences'
import './ProfilePage.css'

export default function CommunityProfilePage() {
  const { profileId } = useParams()
  const { data, loading, error, retry } = useLiteraryPreferences(profileId)
  if (loading) return <div className="page-width page" role="status">Cargando perfil comunitario…</div>
  if (error) return <div className="page-width page"><p role="alert">{error}</p><button className="button primary" type="button" onClick={retry}>Reintentar</button></div>
  return <div className="profile-page page-width reader-profile reader-community-profile">
    <div className="reader-profile-main"><ProfileHeader key={data.id} user={data} publicView /><ProfileAboutSection key={data.id} preferences={data} publicOnly /></div>
  </div>
}
