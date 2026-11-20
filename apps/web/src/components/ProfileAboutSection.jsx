import ReorderableProfileCards from './ReorderableProfileCards'
import ProfileAboutCard from './ProfileAboutCard'
import ProfileTastesCard from './ProfileTastesCard'
import ProfileInterestsCard from './ProfileInterestsCard'
import MostReadGenresCard from './MostReadGenresCard'
import InitialLiteraryDNA from './InitialLiteraryDNA'
import ProfileReadingTastesCard from './ProfileReadingTastesCard'
import ProfileLiteraryHighlights from './ProfileLiteraryHighlights'
import { Pencil, Sprout } from 'lucide-react'
import './ProfilePreferences.css'
import './ProfileAboutSection.css'

export default function ProfileAboutSection({ preferences, biography, loading = false, error = '', onRetry, onSave, publicOnly = false, editMode = false, onToggleEdit, editingControls }) {
  const canEdit = !publicOnly && Boolean(preferences) && !loading && !error
  const editable = canEdit && editMode
  const visible = section => !publicOnly || preferences?.visible_sections?.includes(section)
  return <section className={`reader-about-section${publicOnly ? ' is-public' : ''}`} aria-label="Sobre mí" aria-busy={loading}>
    <header className="reader-about-intro"><Sprout aria-hidden="true" /><div><h2 className="reader-about-title">Mi universo literario</h2></div>{canEdit && <button className="reader-edit-button reader-about-edit-toggle" type="button" aria-label="Editar secciones de Sobre mí" title={editMode ? 'Ocultar botones de edición' : 'Mostrar botones de edición'} aria-pressed={editMode} onClick={onToggleEdit}><Pencil size={14} aria-hidden="true" /></button>}</header>
    {editable && editingControls}
    {loading && <p role="status">Cargando información del perfil…</p>}
    {error && <div className="reader-personal-card"><p role="alert">{error}</p><button className="reader-edit-button" type="button" onClick={onRetry}>Reintentar</button></div>}
    {!loading && !error && <ReorderableProfileCards order={preferences?.card_order} editable={editable} onSave={onSave} cards={[
      visible('biography') && { id: 'history', label: 'Mi historia', wide: true, content: <ProfileAboutCard storyIllustration={preferences?.story_illustration} biography={preferences ? preferences.biography : biography} editable={editable} onSave={onSave} /> },
      visible('biography') && { id: 'crush', label: 'Mi crush literario', content: <ProfileLiteraryHighlights kind="crush" crush={preferences?.literary_crush} editable={editable} onSave={onSave} /> },
      visible('biography') && { id: 'essentials', label: 'Mis libros imprescindibles', content: <ProfileLiteraryHighlights kind="essentials" books={preferences?.essential_books || []} editable={editable} onSave={onSave} /> },
      visible('genres') && { id: 'genres', label: 'Mis géneros favoritos', content: <ProfileAboutCard section="genres" genres={preferences?.genres || []} editable={editable} onSave={onSave} /> },
      visible('tropes') && { id: 'tropes', label: 'Mis tropes', content: <ProfileTastesCard tropes={preferences?.tropes || []} editable={editable} onSave={onSave} /> },
      visible('intensities') && { id: 'featured', label: 'Mis gustos de lectura', wide: true, content: <ProfileReadingTastesCard intensities={preferences?.intensities || []} featuredCategoryId={preferences?.featured_category_id} editable={editable} onSave={onSave} /> },
      !publicOnly && { id: 'statistics', label: 'Mis géneros más leídos', content: <MostReadGenresCard /> },
      !publicOnly && { id: 'recommendations', label: 'Primeras recomendaciones', content: <InitialLiteraryDNA compact /> },
      visible('interests') && { id: 'interests', label: 'Mis intereses', wide: true, content: <ProfileInterestsCard interests={preferences?.interests || []} editable={editable} onSave={onSave} /> },
    ].filter(Boolean)} />}
  </section>
}
