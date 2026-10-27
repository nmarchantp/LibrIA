import { BookHeart, Target } from 'lucide-react'
import { Link } from 'react-router-dom'
import './ProfilePreferences.css'

export default function ProfilePersonalColumn({ preferences }) {
  return <aside className="reader-personal-column" aria-label="Tu espacio personal">
    <section className="reader-personal-card"><h2><Target size={19} aria-hidden="true" />Mi reto de lectura</h2><div className="reader-empty-emblem" aria-hidden="true"><BookHeart size={32} strokeWidth={1.25} /></div><h3>Tu próxima aventura</h3><p className="reader-module-empty">Todavía no hay un reto configurado. Aquí podrás encontrar tu meta cuando esta función esté disponible.</p></section>
    {preferences?.profile_id && <Link className="reader-public-profile-link" to={`/profiles/${preferences.profile_id}`}>Ver mi perfil comunitario</Link>}
  </aside>
}
