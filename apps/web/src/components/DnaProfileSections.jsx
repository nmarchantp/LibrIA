import { BookOpen, Drama, Eye, Feather, Flame, Ghost, Globe, Heart, Lightbulb, NotebookPen, School, Shuffle, Smile, Sparkles, Star, Swords, UserRound, Users, WandSparkles, Zap } from 'lucide-react'
import './DnaProfileSections.css'

// Gemini returns each section as a list of plain sentences. Everything here is presentation:
// icons are picked from words already in the sentence, and no label is added that the AI did not write.
const sections = [
  { key: 'narrative_preferences', label: 'Preferencias narrativas', icon: Sparkles, tone: 'violet', unit: ['rasgo', 'rasgos'], area: 'narrative',
    tip: 'Valora y reseña los libros que terminas para descubrir qué tipo de historias disfrutas.' },
  { key: 'character_preferences', label: 'Personajes', icon: Users, tone: 'rose', unit: ['referente', 'referentes'], area: 'characters', variant: 'characters',
    tip: 'Menciona en tus reseñas a los personajes que te marcaron.' },
  { key: 'themes_and_conflicts', label: 'Temas y conflictos', icon: Flame, tone: 'violet', unit: ['tema', 'temas'], area: 'themes', compact: true,
    tip: 'Tus valoraciones y reseñas revelan los temas que más te atrapan.' },
  { key: 'emotional_patterns', label: 'Respuestas expresadas', icon: Heart, tone: 'rose', unit: ['respuesta', 'respuestas'], area: 'emotions', variant: 'soft',
    note: 'Detectado en tus reseñas y notas de cierre.',
    tip: 'Escribe una reflexión al terminar un libro para conocer cómo te hizo sentir.' },
  { key: 'rating_patterns', label: 'Patrones de valoración', icon: Star, tone: 'amber', unit: ['patrón', 'patrones'], area: 'ratings', variant: 'ratings',
    tip: 'Valora con estrellas los libros que terminas.' },
  { key: 'genres_and_styles', label: 'Géneros y estilos', icon: BookOpen, tone: 'violet', unit: ['detectado', 'detectados'], area: 'genres', variant: 'chips',
    tip: 'Agrega y valora libros de distintos géneros a tu biblioteca.' },
  { key: 'interests_from_notes_and_theories', label: 'Intereses en notas y teorías', icon: NotebookPen, tone: 'violet', unit: ['interés', 'intereses'], area: 'interests',
    tip: 'Añade notas o teorías en tus lecturas para desbloquear este análisis.' },
]

// Keyword → icon, matched without accents. The first match wins; the section icon is the fallback.
const keywordIcons = [
  [/accion|ritmo|adrenalina|trepidante|batalla|combate|lucha/, Zap],
  [/mundo|universo|worldbuilding|ambientacion/, Globe],
  [/giro|tension|suspens|misterio|intriga/, Shuffle],
  [/sorpres|inesperad|revelacion/, Eye],
  [/romance|romantic|amor|pareja/, Heart],
  [/magia|magic|hechiz|fantasia/, WandSparkles],
  [/escuela|academia|entrenamiento|colegio/, School],
  [/terror|miedo|oscur|horror|sobrenatural|paranormal/, Ghost],
  [/guerra|militar|dragon|espada/, Swords],
  [/amistad|vinculo|relacion|familia|lealtad/, Users],
  [/protagonista|personaje|heroin|heroe/, UserRound],
  [/emocion|disfrut|satisfac|alegr|entusiasm/, Smile],
  [/drama|conflicto|dilema|moral/, Drama],
  [/teoria|idea|reflexion|pregunta/, Lightbulb],
  [/estilo|prosa|narrador|escritura|poetic/, Feather],
]
const plain = text => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
const iconFor = (text, fallback) => keywordIcons.find(([pattern]) => pattern.test(plain(text)))?.[1] || fallback

// A proper name written in the sentence ("…como Violet"), so the card can show its initial.
function nameIn(text) {
  const match = text.match(/\bcomo\s+([A-ZÁÉÍÓÚÑ][\p{L}'-]+)/u)
  return match?.[1] || null
}
// Star threshold written in the sentence ("…de 4 estrellas…").
function starsIn(text) {
  const match = plain(text).match(/(\d(?:[.,]\d)?)\s*(?:\+\s*)?estrellas?/)
  return match ? match[1].replace('.', ',') : null
}

function Item({ text, section }) {
  if (section.variant === 'characters') {
    const name = nameIn(text)
    return <li className="dna-item is-character">
      <span className="dna-avatar" aria-hidden="true">{name ? name.charAt(0) : <UserRound size={18} />}</span>
      <span className="dna-item-copy">{name && <strong>{name}</strong>}<span>{text}</span></span>
    </li>
  }
  if (section.variant === 'ratings') {
    const stars = starsIn(text)
    return <li className="dna-item is-plain">
      <span className="dna-item-copy">{stars && <span className="dna-stars"><Star size={12} aria-hidden="true" />{stars}+ estrellas</span>}<span>{text}</span></span>
    </li>
  }
  if (section.variant === 'soft') return <li className="dna-item is-soft"><span>{text}</span></li>
  const Icon = iconFor(text, section.icon)
  return <li className="dna-item"><span className="dna-item-icon" aria-hidden="true"><Icon size={15} /></span><span className="dna-item-copy"><span>{text}</span></span></li>
}

function Section({ section, items }) {
  const Icon = section.icon
  const count = items.length
  const empty = count === 0
  return <article className={`dna-card dna-section is-${section.tone}${empty ? ' is-empty' : ''}`} style={{ gridArea: section.area }}>
    <header className="dna-section-head">
      <span className="dna-section-icon" aria-hidden="true"><Icon size={18} /></span>
      <h3>{section.label}</h3>
      {!empty && <span className={`dna-count${section.variant === 'chips' ? ' is-pill' : ''}`}>{count} {count === 1 ? section.unit[0] : section.unit[1]}</span>}
    </header>
    {empty ? <>
      <p className="dna-muted">Sin hallazgos suficientemente respaldados.</p>
      <div className="dna-unlock"><strong>Cómo desbloquearlo</strong><p>{section.tip}</p></div>
    </> : section.variant === 'chips'
      ? <ul className="dna-chips">{items.map((item, index) => <li key={index}>{item}</li>)}</ul>
      : <ul className={`dna-items${section.compact ? ' is-compact' : ''}`}>{items.map((item, index) => <Item key={index} text={item} section={section} />)}</ul>}
    {!empty && section.note && <p className="dna-section-note">{section.note}</p>}
  </article>
}

export default function DnaProfileSections({ content }) {
  // The wrapper is the size container: the grid adapts to its own column, not to the window.
  return <div className="dna-bento-wrap"><div className="dna-bento">
    {sections.map(section => <Section key={section.key} section={section} items={Array.isArray(content[section.key]) ? content[section.key].filter(Boolean) : []} />)}
  </div></div>
}
