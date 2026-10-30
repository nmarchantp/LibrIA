import { useState } from 'react'
import { CalendarDays } from 'lucide-react'
import ProfileBanner from './ProfileBanner'
import { apiAssetUrl } from '../api/client'

export default function ProfileHeader({ user, publicView = false }) {
  const [failedAvatar, setFailedAvatar] = useState(null)
  const initials = user.display_name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('')
  const joined = user.created_at ? new Date(user.created_at) : null
  const joinedLabel = joined && !Number.isNaN(joined.getTime()) ? new Intl.DateTimeFormat('es-CL', { month: 'long', year: 'numeric' }).format(joined) : null
  return <>
    {/* Dedicated cover slot: no upload/edit controls until real persistence exists. */}
    <ProfileBanner />
    <header className="reader-profile-identity">
      <div className="reader-profile-avatar">{user.avatar_url && failedAvatar !== user.avatar_url ? <img key={user.avatar_url} src={apiAssetUrl(user.avatar_url)} alt="" onError={() => setFailedAvatar(user.avatar_url)} /> : initials}</div>
      <div className="reader-profile-name"><span className="kicker">{publicView ? 'PERFIL DE LA COMUNIDAD' : 'MI PERFIL'}</span><h1>{user.display_name}</h1><p>Un refugio para todos los mundos que habitan en ti.</p>{!publicView && joinedLabel && <span className="reader-profile-joined"><CalendarDays size={15} aria-hidden="true" />Miembro desde {joinedLabel}</span>}</div>
    </header>
  </>
}
