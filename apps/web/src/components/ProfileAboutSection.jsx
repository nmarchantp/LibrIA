import ProfileAboutCard from './ProfileAboutCard'
import ProfileTastesCard from './ProfileTastesCard'
import MostReadGenresCard from './MostReadGenresCard'
import ProfileReadingTastesCard from './ProfileReadingTastesCard'
import { Pencil, Sprout } from 'lucide-react'
import './ProfilePreferences.css'
import './ProfileAboutSection.css'

export default function ProfileAboutSection({ preferences, biography, loading = false, error = '', onRetry, onSave, publicOnly = false, editMode = false, onToggleEdit }) {
  const canEdit = !publicOnly && Boolean(preferences) && !loading && !error
  const editable = canEdit && editMode
  return <section className={`reader-about-section${publicOnly ? ' is-public' : ''}`} aria-label="Sobre mí" aria-busy={loading}>
    <header className="reader-about-intro"><Sprout aria-hidden="true" /><div><h2 className="reader-about-title">Sobre mí</h2></div>{canEdit && <button className="reader-edit-button reader-about-edit-toggle" type="button" aria-label="Editar secciones de Sobre mí" title={editMode ? 'Ocultar botones de edición' : 'Mostrar botones de edición'} aria-pressed={editMode} onClick={onToggleEdit}><Pencil size={14} aria-hidden="true" /></button>}</header>
    {loading && <p role="status">Cargando información del perfil…</p>}
    {error && <div className="reader-personal-card"><p role="alert">{error}</p><button className="reader-edit-button" type="button" onClick={onRetry}>Reintentar</button></div>}
    {!loading && !error && <div className="reader-about-grid">
      <ProfileAboutCard storyIllustration={preferences?.story_illustration} biography={preferences ? preferences.biography : biography} editable={editable} onSave={onSave} />
      <ProfileAboutCard section="genres" genres={preferences?.genres || []} editable={editable} onSave={onSave} />
      <ProfileTastesCard tropes={preferences?.tropes || []} editable={editable} onSave={onSave} />
      <ProfileReadingTastesCard intensities={preferences?.intensities || []} featuredCategoryId={preferences?.featured_category_id} editable={editable} onSave={onSave} />
      {!publicOnly && <MostReadGenresCard />}
    </div>}
  </section>
}
