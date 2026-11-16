import { CalendarDays, Feather } from 'lucide-react'
import ProfileBanner from './ProfileBanner'
import { ProfileStoryAvatar } from './UserStories'

export default function ProfileHeader({ user, publicView = false, statistics, panoramic = false }) {
  const joined = user.created_at ? new Date(user.created_at) : null
  const joinedLabel = joined && !Number.isNaN(joined.getTime()) ? new Intl.DateTimeFormat('es-CL', { month: 'long', year: 'numeric' }).format(joined) : null
  return <>
    {/* Dedicated cover slot: no upload/edit controls until real persistence exists. */}
    <ProfileBanner panoramic={panoramic} />
    <header className="reader-profile-identity">
      <ProfileStoryAvatar user={user} publicView={publicView} />
      <div className="reader-profile-name"><span className="kicker">{publicView ? 'PERFIL DE LA COMUNIDAD' : panoramic ? `LECTOR${user.role === 'admin' ? ' · ADMINISTRADOR' : ''}` : 'MI PERFIL'}</span><div className="reader-profile-title-row"><h1>{user.display_name}{panoramic && <Feather className="reader-profile-name-feather" size={23} aria-hidden="true" />}</h1>{!panoramic && statistics}</div>{panoramic && user.username && <span className="reader-profile-handle">@{user.username.replace(/^@/, '')}</span>}{(!publicView || user.can_view) && <p>Un refugio para todos los mundos que habitan en ti. ✨</p>}{!publicView && joinedLabel && <span className="reader-profile-joined"><CalendarDays size={15} aria-hidden="true" />Miembro desde {joinedLabel}</span>}</div>
      {panoramic && statistics}
    </header>
  </>
}
