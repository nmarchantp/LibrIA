import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useLibrary } from '../context/LibraryContext'
import BookCover from './BookCover'
import { apiAssetUrl } from '../api/client'
import { onboardingService } from '../services/onboardingService'
import './RegistrationWizard.css'

export default function InitialLiteraryDNA({ initial = null, sharing = false, motionEnabled = true }) {
  const [state, setState] = useState(initial)
  const [error, setError] = useState('')
  const [added, setAdded] = useState([])
  const [pending, setPending] = useState('')
  const [slide, setSlide] = useState(0)
  const [paused, setPaused] = useState(false)
  const [playRequested, setPlayRequested] = useState(false)
  const [hidden, setHidden] = useState(document.hidden)
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const recommendations = state?.recommendations || []
  const currentSlide = slide % Math.max(1, recommendations.length)
  const selected = recommendations[currentSlide]
  const autoPlaying = (playRequested || (motionEnabled && !reducedMotion)) && !paused
  const { addBook } = useLibrary()
  const completed = state?.status === 'completed'
  useEffect(() => {
    if (!completed) return
    let active = true
    onboardingService.syncFavorites().then(() => {
      if (active) window.dispatchEvent(new Event('libria:catalog-identity-changed'))
    }).catch(error => { if (active) setError(error.message) })
    return () => { active = false }
  }, [completed])
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const updateMotion = () => setReducedMotion(media.matches)
    const updateVisibility = () => setHidden(document.hidden)
    media.addEventListener('change', updateMotion)
    document.addEventListener('visibilitychange', updateVisibility)
    return () => { media.removeEventListener('change', updateMotion); document.removeEventListener('visibilitychange', updateVisibility) }
  }, [])
  useEffect(() => {
    if (!autoPlaying || hidden || pending || recommendations.length < 2) return
    const timer = setTimeout(() => setSlide(value => (value + 1) % recommendations.length), 5000)
    return () => clearTimeout(timer)
  }, [autoPlaying, hidden, pending, recommendations.length, slide])
  const move = next => setSlide((next + recommendations.length) % recommendations.length)
  useEffect(() => {
    let active = true
    let timer
    let attempts = 0
    const poll = async () => {
      try {
        const value = await onboardingService.get()
        if (!active) return
        setState(value); setError('')
        // Bound automatic polling. Access never depends on generation success.
        if (value.ai_available !== false && ['pending', 'processing'].includes(value.ai_status) && value.status === 'completed' && ++attempts < 15) timer = setTimeout(poll, 4000)
      } catch (error) { if (active) setError(error.message) }
    }
    poll()
    return () => { active = false; clearTimeout(timer) }
  }, [])
  const add = async item => {
    if (pending) return
    setPending(item.work_id)
    try {
      await addBook({ id: item.work_id, workId: item.work_id, canonicalWorkId: item.work_id, title: item.title,
        author: (item.authors || []).join(', '), editionId: item.edition_id, editionOptional: !item.edition_id, image: item.cover_url })
      setAdded(current => [...current, item.work_id])
    } catch (error) { setError(error.message) }
    finally { setPending('') }
  }
  const share = async event => {
    const shared = event.target.checked
    try { await onboardingService.share(shared); setState(current => ({ ...current, shared })) }
    catch (error) { setError(error.message) }
  }
  return <section className="initial-literary-dna" aria-label="Mi ADN literario">
    <h2>Mi ADN literario</h2>
    {error && <p role="alert">{error}</p>}
    {!state && !error && <p role="status">Cargando tus recomendaciones…</p>}
    {state?.status !== 'completed' && state && <p><Link to="/register?edit=true">Completar mi cuestionario literario</Link></p>}
    {state?.status === 'completed' && <>
      <h3>Recomendaciones de tu cuestionario</h3>
      <p className="registration-recommendation-source">{state.recommendation_source === 'gemini'
        ? 'La IA eligió estos libros según tus respuestas y favoritos del cuestionario.'
        : 'Estas sugerencias del catálogo priorizan tus géneros y suman otras historias para explorar.'}</p>
      {recommendations.length === 0 && state.ai_status !== 'completed' && <p role="status">{state.ai_status === 'failed' || state.ai_available === false || state.ai_error_code
        ? 'La consulta a la IA no estuvo disponible. Puedes explorar estas sugerencias del catálogo.'
        : 'Buscando recomendaciones con IA a partir de tus respuestas. Puedes explorar las sugerencias disponibles mientras termina.'}</p>}
      {selected ? <div className="registration-recommendation-gallery" role="region" aria-roledescription="carrusel" aria-label="Libros recomendados" onFocusCapture={event => { if (event.target.matches(':focus-visible') && !event.target.closest('.registration-carousel-play')) setPaused(true) }}>
        <div className="registration-recommendation-covers">
        <div className="registration-book-carousel">
          {recommendations.map((item, index) => {
            let offset = (index - currentSlide + recommendations.length) % recommendations.length
            if (offset > recommendations.length / 2) offset -= recommendations.length
            return <button key={item.work_id} type="button" className={`registration-carousel-cover${offset === 0 ? ' is-current' : ''}`} hidden={Math.abs(offset) > 1} style={{ '--carousel-offset': offset, transition: autoPlaying ? 'transform 2400ms ease-in-out, opacity 2400ms ease-in-out' : undefined }} aria-label={`Ver recomendación: ${item.title}`} aria-pressed={offset === 0} onClick={() => move(index)}>
              <BookCover large book={{ title: item.title, author: [...new Set(item.authors || [])].join(', '), image: apiAssetUrl(item.cover_url), initial: item.title[0], color: '#654184', accent: '#fff4db' }} />
            </button>
          })}
        </div>
        {recommendations.length > 1 && <div className="registration-carousel-controls" aria-label="Controles de recomendaciones">
          <button type="button" aria-label="Libro anterior" onClick={() => move(currentSlide - 1)}>←</button>
          <span>{currentSlide + 1} de {recommendations.length}</span>
          <button type="button" aria-label="Libro siguiente" onClick={() => move(currentSlide + 1)}>→</button>
          <button type="button" className="registration-carousel-play" aria-label={autoPlaying ? 'Pausar carrusel' : 'Reanudar carrusel'} onClick={() => { if (autoPlaying) setPaused(true); else { setPlayRequested(true); setPaused(false) } }}>{autoPlaying ? 'Pausar' : 'Reanudar'}</button>
        </div>}
        </div>
        <article className="registration-recommendation-detail" aria-live={autoPlaying ? 'off' : 'polite'}>
          <h4>{selected.title}</h4><p className="registration-recommendation-author">{[...new Set(selected.authors || [])].join(', ')}</p><p>{selected.explanation}</p>
          <button type="button" className="button primary registration-recommendation-add" aria-busy={pending === selected.work_id} disabled={Boolean(pending) || added.includes(selected.work_id)} onClick={() => add(selected)}>{added.includes(selected.work_id) ? 'En tu biblioteca' : pending === selected.work_id ? 'Agregando…' : 'Añadir a mi biblioteca'}</button>
        </article>
      </div> : <p>Aún no hay recomendaciones disponibles para tus preferencias.</p>}
      <details className="registration-dna-details"><summary>Mis afinidades según el cuestionario</summary>
        {state.dna && <><h3>{state.dna.profile_name}</h3><p>{state.dna.profile_description}</p><p>{(state.dna.preferred_genres || []).join(' · ')}</p><p>{state.dna.explanation}</p></>}
        <p>Esta primera aproximación utiliza tus preferencias declaradas; todavía no analiza tu historial de lecturas.</p>
        {state.generated_at && <small>Actualizado el {new Date(state.generated_at).toLocaleDateString('es-CL')}</small>}
      </details>
      <aside className="registration-dna-future"><strong>Tu ADN seguirá creciendo</strong><p>Más adelante podrás profundizar con IA en tu biblioteca completa y cada lectura.</p></aside>
      {sharing && <label><input type="checkbox" checked={Boolean(state.shared)} onChange={share} />Compartir mis afinidades literarias en Sobre mí</label>}
    </>}
  </section>
}
