import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLibrary } from '../context/LibraryContext'
import { onboardingService } from '../services/onboardingService'
import './WelcomeGuide.css'

const steps = {
  analysis: ['Tu punto de partida literario', 'Aquí reunimos las afinidades y recomendaciones de tu cuestionario. Tus favoritos ya están en tu biblioteca como Pendiente; las lecturas que registres permitirán profundizar después.', '.initial-literary-dna', 'Explorar libros'],
  search: ['Busca una historia que quieras leer', 'En Explorar libros puedes buscar por título, autor o ISBN. Escribe el nombre de un libro que te interese; también puedes usar una sugerencia del buscador.', '.catalog-search-panel', 'Ir al buscador'],
  choose: ['Elige el libro correcto', 'Abre un resultado y revisa su título, autor y edición. Si no es el que buscas, cambia la búsqueda o prueba por ISBN.', '.catalog-result-card', 'Ver los resultados'],
  add: ['Guárdalo en tu biblioteca', 'Revisa la ficha y pulsa Agregar a biblioteca. Si hay varias ediciones, elige la tuya; cuando esté disponible también puedes guardar la obra sin edición.', '.detail-library-action', 'Ir al botón del libro'],
  library: ['Tu libro ya tiene un lugar', 'Esta es Mi biblioteca, dentro de tu perfil. Los libros nuevos quedan como Pendiente. Usa los filtros para encontrar tus lecturas y abre una portada para gestionarla.', '.reader-library-grid', 'Abrir mi lectura'],
  manage: ['Decide cuándo empezar', 'Aquí puedes cambiar el estado de tu lectura. Déjala como Pendiente hasta que quieras comenzarla; no necesitas cambiarla para seguir con la guía.', '.reading-status-picker', 'Conocer el progreso'],
  progress: ['Registra tu avance', 'Cuando estés leyendo, guarda tu página actual y, si lo conoces, el total de páginas. El progreso se conserva en tu biblioteca.', '.compact-progress-editor', 'Conocer el cuaderno'],
  notebook: ['Conserva lo que te deja la lectura', 'En Cuaderno puedes guardar tus reflexiones. También encontrarás valoración, notas y teorías: esa información ayuda a construir análisis más profundos de tu lectura y biblioteca.', '.reading-tabs', 'Terminar guía'],
}
const order = Object.keys(steps)
const findTarget = selector => [...document.querySelectorAll(selector)].find(element => element.getClientRects().length && !element.closest('[hidden], [inert]'))
const routeFor = guide => {
  if (guide.step === 'analysis') return '/profile?tab=analysis'
  if (guide.step === 'library') return '/profile?tab=library'
  if (['manage', 'progress', 'notebook'].includes(guide.step)) return guide.book_ref ? `/library/${encodeURIComponent(guide.book_ref)}` : '/profile?tab=library'
  if (guide.step === 'add' && guide.book_ref) return `/books/${encodeURIComponent(guide.book_ref)}`
  return '/books'
}

export default function WelcomeGuide() {
  const { user } = useAuth()
  const { books } = useLibrary()
  const location = useLocation()
  const navigate = useNavigate()
  const navigator = useRef(navigate)
  navigator.current = navigate
  const [guide, setGuide] = useState(null)
  const [questionnaire, setQuestionnaire] = useState(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const busy = useRef(false)
  const mounted = useRef(true)
  const current = useRef(null)
  current.current = guide
  const userId = user?.id
  const identity = useRef(userId)
  identity.current = userId
  const enabled = user?.role === 'lector' && !user?.onboarding_required
  const advance = useCallback(async (step, bookRef) => {
    if (busy.current) return null
    busy.current = true; setSaving(true); setError('')
    const requestedUser = identity.current
    try {
      const next = await onboardingService.guide(step, bookRef)
      if (!mounted.current || identity.current !== requestedUser) return null
      setGuide(next)
      return next
    } catch (error) { if (mounted.current) setError(error.message); return null }
    finally { busy.current = false; if (mounted.current) setSaving(false) }
  }, [])

  useEffect(() => {
    mounted.current = true
    let active = true
    setGuide(null)
    setQuestionnaire(null)
    if (enabled) Promise.all([onboardingService.get(), onboardingService.catalogs().catch(() => null)]).then(([value, catalogs]) => {
      if (!active) return
      setQuestionnaire({ ...value.answers, genres: catalogs?.genres?.filter(item => value.answers?.genre_ids?.includes(item.id)).map(item => item.name) || value.dna?.preferred_genres || [] })
      if (!steps[value.guide?.step]) return
      setGuide(value.guide)
      navigator.current(routeFor(value.guide), { replace: true })
    }).catch(() => { /* Existing navigation remains usable when the guide cannot load. */ })
    return () => { active = false; mounted.current = false }
  }, [userId, enabled])

  useEffect(() => {
    if (!enabled) return
    const searchResults = () => { if (current.current?.step === 'search') advance('choose') }
    const added = event => {
      if (['search', 'choose', 'add'].includes(current.current?.step)) advance('library', String(event.detail.bookRef)).then(next => { if (next) navigate(routeFor(next)) })
    }
    const start = () => advance('analysis').then(next => { if (next) navigate(routeFor(next)) })
    window.addEventListener('libria:guide-search-results', searchResults)
    window.addEventListener('libria:library-book-added', added)
    window.addEventListener('libria:start-welcome-guide', start)
    return () => {
      window.removeEventListener('libria:guide-search-results', searchResults)
      window.removeEventListener('libria:library-book-added', added)
      window.removeEventListener('libria:start-welcome-guide', start)
    }
  }, [advance, navigate, enabled])

  useEffect(() => {
    if (!guide || saving) return
    if (['search', 'choose', 'add'].includes(guide.step) && /^\/books\/[^/]+$/.test(location.pathname) && (guide.step !== 'add' || guide.book_ref !== decodeURIComponent(location.pathname.slice('/books/'.length)))) {
      advance('add', decodeURIComponent(location.pathname.slice('/books/'.length)))
    } else if (guide.step === 'search' && location.pathname === '/books' && document.querySelector('.catalog-result-card')) {
      advance('choose')
    } else if (guide.step === 'library' && location.pathname.startsWith('/library/')) {
      advance('manage', decodeURIComponent(location.pathname.slice('/library/'.length)))
    }
  }, [guide, location.pathname, saving, advance])

  useEffect(() => {
    if (!steps[guide?.step]) return
    let target
    const reveal = () => {
      const next = findTarget(steps[guide.step][2])
      if (!next || next === target) return
      target?.removeAttribute('data-welcome-focus')
      target = next
      target.setAttribute('data-welcome-focus', 'true')
      if (guide.step === 'choose' && document.activeElement?.matches('.catalog-search-input input')) return
      if (window.matchMedia('(min-width: 701px)').matches) target.scrollIntoView({ block: 'center', behavior: 'instant' })
      else document.querySelector('.welcome-guide')?.scrollIntoView({ block: 'start', behavior: 'instant' })
    }
    const observer = new MutationObserver(reveal)
    observer.observe(document.getElementById('main-content') || document.body, { childList: true, subtree: true })
    reveal()
    return () => { observer.disconnect(); target?.removeAttribute('data-welcome-focus') }
  }, [guide?.step, location.pathname, location.search])

  if (!enabled || !steps[guide?.step]) return null
  const [title, description, selector, label] = steps[guide.step]
  const expectedRoute = routeFor(guide)
  const [expectedPath, expectedSearch] = expectedRoute.split('?')
  const onRoute = decodeURIComponent(location.pathname) === decodeURIComponent(expectedPath) && (!expectedSearch || new URLSearchParams(location.search).get('tab') === new URLSearchParams(expectedSearch).get('tab'))
  const selectedBook = books.find(book => [book.id, book.workId, book.canonicalWorkId, book.externalId].some(id => id != null && String(id) === guide.book_ref))
  const go = async () => {
    if (!onRoute) { navigate(expectedRoute); return }
    if (guide.step === 'analysis') {
      const next = await advance('search'); if (next) navigate(routeFor(next))
    } else if (guide.step === 'add' && selectedBook) {
      const next = await advance('library', String(selectedBook.id)); if (next) navigate(routeFor(next))
    } else if (guide.step === 'library') {
      const book = selectedBook || books[0]
      if (book) { const next = await advance('manage', String(book.id)); if (next) navigate(routeFor(next)) }
      else { const next = await advance('search'); if (next) navigate(routeFor(next)) }
    } else if (guide.step === 'manage') await advance('progress')
    else if (guide.step === 'progress') {
      const next = await advance('notebook')
      if (next) document.querySelector('[data-guide-notebook]')?.click()
    } else if (guide.step === 'notebook') await advance('completed')
    else {
      const target = findTarget(guide.step === 'search' ? '.catalog-search-input input' : selector)
      target?.scrollIntoView({ block: 'center', behavior: 'smooth' }); target?.focus()
    }
  }
  return <aside className="welcome-guide" aria-labelledby="welcome-guide-title" aria-busy={saving}>
    <div className="welcome-guide-copy" aria-live="polite"><span className="welcome-guide-kicker">Tu primer recorrido · {order.indexOf(guide.step) + 1} de {order.length}</span><h2 id="welcome-guide-title">{title}</h2><p>{description}</p>{guide.step === 'analysis' && questionnaire && <p className="welcome-guide-summary">{[questionnaire.genres?.join(', '), questionnaire.emotions?.join(', '), questionnaire.habit, `${questionnaire.favorite_work_ids?.length || 0} favoritos`].filter(Boolean).join(' · ')}</p>}{error && <p role="alert">No pudimos guardar este paso: {error} Inténtalo nuevamente.</p>}</div>
    <div className="welcome-guide-actions"><button className="button primary" type="button" disabled={saving} onClick={go}>{!onRoute ? 'Retomar este paso' : guide.step === 'add' && selectedBook ? 'Ver mi biblioteca' : label}</button><button className="button text" type="button" disabled={saving} onClick={() => advance('dismissed')}>Omitir guía</button></div>
  </aside>
}
