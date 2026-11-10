import { CalendarDays } from 'lucide-react'
import ProfileBanner from './ProfileBanner'
import { ProfileStoryAvatar } from './UserStories'

export default function ProfileHeader({ user, publicView = false }) {
  const joined = user.created_at ? new Date(user.created_at) : null
  const joinedLabel = joined && !Number.isNaN(joined.getTime()) ? new Intl.DateTimeFormat('es-CL', { month: 'long', year: 'numeric' }).format(joined) : null
  return <>
    {/* Dedicated cover slot: no upload/edit controls until real persistence exists. */}
    <ProfileBanner />
    <header className="reader-profile-identity">
      <ProfileStoryAvatar user={user} publicView={publicView} />
      <div className="reader-profile-name"><span className="kicker">{publicView ? 'PERFIL DE LA COMUNIDAD' : 'MI PERFIL'}</span><h1>{user.display_name}</h1>{(!publicView || user.can_view) && <p>Un refugio para todos los mundos que habitan en ti.</p>}{!publicView && joinedLabel && <span className="reader-profile-joined"><CalendarDays size={15} aria-hidden="true" />Miembro desde {joinedLabel}</span>}</div>
    </header>
  </>
}
