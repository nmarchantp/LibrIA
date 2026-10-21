import { useState } from 'react'
import { BookCheck, BookOpen, CalendarDays, Library, Bookmark } from 'lucide-react'
import ProfileBanner from './ProfileBanner'

export default function ProfileHeader({ user, books, loading, loadError }) {
  const [avatarFailed, setAvatarFailed] = useState(false)
  const initials = user.display_name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('')
  const joined = user.created_at ? new Date(user.created_at) : null
  const joinedLabel = joined && !Number.isNaN(joined.getTime()) ? new Intl.DateTimeFormat('es-CL', { month: 'long', year: 'numeric' }).format(joined) : null
  const stats = [
    { label: 'Libros', value: books.length, Icon: Library },
    { label: 'Leyendo', value: books.filter(book => book.status === 'Leyendo').length, Icon: BookOpen },
    { label: 'Terminados', value: books.filter(book => book.status === 'Terminado').length, Icon: BookCheck },
    { label: 'Pendientes', value: books.filter(book => book.status === 'Pendiente').length, Icon: Bookmark },
  ]
  return <>
    {/* Dedicated cover slot: no upload/edit controls until real persistence exists. */}
    <ProfileBanner />
    <header className="reader-profile-identity">
      <div className="reader-profile-avatar">{user.avatar_url && !avatarFailed ? <img key={user.avatar_url} src={user.avatar_url} alt="" onError={() => setAvatarFailed(true)} /> : initials}</div>
      <div className="reader-profile-name"><span className="kicker">MI PERFIL</span><h1>{user.display_name}</h1><p>Un refugio para todos los mundos que habitan en ti.</p>{joinedLabel && <span className="reader-profile-joined"><CalendarDays size={15} aria-hidden="true" />Miembro desde {joinedLabel}</span>}</div>
    </header>
    <dl className="reader-profile-stats" aria-label="Estadísticas de tu biblioteca" aria-busy={loading}>
      {stats.map(({ label, value, Icon }) => <div className="reader-profile-stat" key={label}><span className="reader-profile-stat-icon"><Icon size={25} strokeWidth={1.5} aria-hidden="true" /></span><div><dt>{label}</dt><dd>{loading || loadError ? '—' : value}</dd></div></div>)}
    </dl>
    {loadError && <p className="reader-profile-stat-notice" role="status">Las estadísticas no están disponibles mientras no se pueda cargar la biblioteca.</p>}
  </>
}
