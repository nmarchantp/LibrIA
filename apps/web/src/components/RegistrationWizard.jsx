import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { BookOpen } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useAuthJourney } from '../context/AuthJourneyContext'
import { useTheme } from '../context/ThemeContext'
import { onboardingService } from '../services/onboardingService'
import { searchBookCatalog } from '../services/booksService'
import { profileDestination } from '../services/profileDestination'
import RegistrationPasswordFields from './RegistrationPasswordFields'
import InitialLiteraryDNA from './InitialLiteraryDNA'
import LiteraryCoverStack from './LiteraryCoverStack'
import './RegistrationWizard.css'

const headings = ['Crea tu cuenta', '¿Qué mundos te gusta explorar?', '¿Qué te atrapa de una historia?', '¿Qué te gustaría sentir con tu próxima lectura?', '¿Cómo te describirías como lector?', '¿Qué libros han dejado huella en ti?', 'Dale tu propio estilo a tu universo', '¡Tu universo literario comienza aquí!']
const empty = { genre_ids: [], trope_ids: [], emotions: [], habit: null, favorite_work_ids: [], theme: 'lavanda' }

function FavoriteStack({ ids, books, onRemove, className }) {
  if (!ids.length) return null
  return <section className={`registration-favorites ${className}`} aria-label="Libros favoritos seleccionados">
    <div className="registration-favorites-heading"><h3>Tus favoritos</h3><span>{ids.length} de 5</span></div>
    <LiteraryCoverStack books={ids.map((id, index) => ({ ...books[id], id, title: books[id]?.title || `Favorito ${index + 1}` }))} onRemove={onRemove} />
    <p className="registration-favorites-hint">Tu pequeña colección de historias inolvidables.</p>
  </section>
}

function Choices({ options, selected, limit, onChange, single = false }) {
  return <div className="registration-choices" role="group">{options.map(option => {
    const id = option.id ?? option
    const checked = single ? selected === id : selected.includes(id)
    return <button key={id} type="button" aria-pressed={checked} disabled={!checked && !single && selected.length >= limit} className={checked ? 'selected' : ''}
      onClick={() => onChange(single ? id : checked ? selected.filter(value => value !== id) : [...selected, id])}><span aria-hidden="true">{checked ? '✦' : '＋'}</span> {option.name ?? option}</button>
  })}</div>
}

function PagedChoices({ options, selected, onChange, noun = 'géneros', placeholder = 'Fantasía, romance, misterio…', pageSize = 18 }) {
  const [page, setPage] = useState(0)
  const [query, setQuery] = useState('')
  const normalize = text => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
  const filtered = options.filter(option => normalize(option.name).includes(normalize(query.trim())))
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize))
  const current = Math.min(page, pageCount - 1)
  return <div className="registration-genre-picker">
    <label className="registration-genre-search">Buscar {noun}<input type="search" value={query} onChange={event => { setQuery(event.target.value); setPage(0) }} placeholder={placeholder} /></label>
    <Choices options={filtered.slice(current * pageSize, (current + 1) * pageSize)} selected={selected} limit={5} onChange={onChange} />
    {!filtered.length && <p>No encontramos {noun} con ese nombre.</p>}
    <div className="registration-genre-pagination" aria-label={`Páginas de ${noun}`}>
      <button type="button" disabled={current === 0} onClick={() => setPage(current - 1)} aria-label={`Página anterior de ${noun}`}>←</button>
      <span aria-live="polite">{current + 1} de {pageCount}</span>
      <button type="button" disabled={current + 1 === pageCount} onClick={() => setPage(current + 1)} aria-label={`Página siguiente de ${noun}`}>→</button>
      <span className="registration-genre-count" role="status">{selected.length} de 5 seleccionados</span>
    </div>
  </div>
}

export default function RegistrationWizard() {
  const { user, register, refreshUser, loading: authLoading, logout } = useAuth()
  const { motionEnabled, setMotionEnabled, run: journey } = useAuthJourney()
  const { selectTheme } = useTheme()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [step, setStep] = useState(user ? 1 : 0)
  const [answers, setAnswers] = useState(empty)
  const [catalogs, setCatalogs] = useState({ genres: [], tropes: [] })
  const [catalogError, setCatalogError] = useState('')
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(Boolean(user))
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [bookPage, setBookPage] = useState(0)
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 800px)').matches)
  const bookResultsPerPage = mobile ? 1 : 2
  const bookPageCount = Math.max(1, Math.ceil(results.length / bookResultsPerPage))
  const visibleBookPage = Math.min(bookPage, bookPageCount - 1)
  const [favoriteBooks, setFavoriteBooks] = useState({})
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')
  const busy = useRef(false)
  const creatingAccount = useRef(false)
  const heading = useRef(null)
  const hydrated = useRef(false)
  const [saved, setSaved] = useState('')
  const [transitioning, setTransitioning] = useState(false)
  const [editing, setEditing] = useState(params.get('edit') === 'true')
  const question = step > 0 ? step : null
  const accountVisible = step < 7 && (!mobile || step === 0)
  const [direction, setDirection] = useState('forward')

  useEffect(() => {
    const media = window.matchMedia('(max-width: 800px)')
    const update = () => setMobile(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

  useEffect(() => {
    if (user?.id) return
    let active = true
    setCatalogError('')
    onboardingService.catalogs().then(choices => { if (active) setCatalogs(choices) })
      .catch(() => { if (active) setCatalogError('No pudimos cargar los géneros.') })
    return () => { active = false }
  }, [user?.id, retry])

  useEffect(() => {
    if (!user?.id) {
      hydrated.current = false
      setState(null); setAnswers(empty); setFavoriteBooks({}); setStep(0)
    }
  }, [user?.id])

  useEffect(() => {
    if (!user?.id) return
    let active = true
    hydrated.current = false
    if (!creatingAccount.current) setLoading(true)
    Promise.all([onboardingService.get(), onboardingService.catalogs()]).then(([progress, choices]) => {
      if (!active) return
      setState(progress); setCatalogs(choices); setCatalogError(''); setAnswers(current => ({ ...empty, ...current, ...(editing ? progress.draft_answers || progress.answers : progress.answers) }))
      setFavoriteBooks(Object.fromEntries((progress.favorite_books || []).map(book => [book.work_id, book])))
      setStep(progress.status === 'completed' ? editing ? progress.draft_step || 1 : 7 : Math.min(progress.step || 1, 7))
      hydrated.current = true; setError('')
    }).catch(error => { if (active) setError(error.message) }).finally(() => { if (active) { setLoading(false); creatingAccount.current = false } })
    return () => { active = false }
  }, [user?.id, retry, editing])

  useEffect(() => {
    if (loading) return
    const timer = setTimeout(() => { heading.current?.focus(); setTransitioning(false) }, motionEnabled ? 400 : 0)
    return () => clearTimeout(timer)
  }, [step, motionEnabled, loading])

  useEffect(() => {
    if (!user || !hydrated.current || !state || (state.status === 'completed' && !editing) || pending) return
    const timer = setTimeout(() => {
      onboardingService.save({ step: Math.max(1, step), answers }).then(() => setSaved('Progreso guardado'))
        .catch(() => setSaved('No se guardó el último cambio. Pulsa Siguiente para reintentar.'))
    }, 700)
    return () => clearTimeout(timer)
  }, [answers, step, user, state, pending, editing])

  useEffect(() => {
    setBookPage(0)
    if (step !== 5 || !query.trim()) { setResults([]); return }
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      setSearching(true); setSearchError('')
      try {
        const result = await searchBookCatalog(query, 'all', { signal: controller.signal, localOnly: true })
        if (!controller.signal.aborted) setResults([...new Map(result.books.filter(book => book.canonicalWorkId).map(book => [book.canonicalWorkId, book])).values()])
      } catch (error) { if (!controller.signal.aborted) setSearchError(error.message) }
      finally { if (!controller.signal.aborted) setSearching(false) }
    }, 300)
    return () => { clearTimeout(timer); controller.abort() }
  }, [query, step])

  const update = (key, value) => { setAnswers(current => ({ ...current, [key]: value })); setSaved(user ? 'Guardando…' : '') }
  const removeFavorite = id => {
    setAnswers(current => ({ ...current, favorite_work_ids: current.favorite_work_ids.filter(value => value !== id) }))
    setSaved(user ? 'Guardando…' : '')
  }
  const move = next => { setDirection(next < step ? 'backward' : 'forward'); setTransitioning(true); setStep(next); setError('') }
  const submit = async event => {
    event.preventDefault()
    if (busy.current || transitioning || loading) return
    setError('')
    if (step === 0) {
      if (user) { move(1); return }
      const form = new FormData(event.currentTarget)
      if (form.get('password') !== form.get('password_confirmation')) { setError('Las contraseñas no coinciden.'); return }
      busy.current = true; setPending(true)
      creatingAccount.current = true
      try {
        const result = await register({ display_name: form.get('name'), email: form.get('email'), password: form.get('password') })
        if (result?.status !== 'registered') move(1)
      } catch (error) { creatingAccount.current = false; setError('No fue posible crear la cuenta. ' + error.message) }
      finally { busy.current = false; setPending(false) }
      return
    }
    const required = { 1: answers.genre_ids.length, 2: answers.trope_ids.length, 3: answers.emotions.length, 4: answers.habit }
    if (step in required && !required[step]) { setError('Selecciona al menos una opción para continuar.'); return }
    busy.current = true; setPending(true)
    try {
      const complete = step === 7
      const next = Math.min(step + 1, 7)
      const progress = await onboardingService.save({ step: next, answers, complete })
      setState(progress); setSaved('Progreso guardado')
      if (complete) { setEditing(false); await refreshUser() }
      else move(next)
    } catch (error) { setError(error.message) }
    finally { busy.current = false; setPending(false) }
  }
  const back = async () => {
    if (busy.current || step <= 0 || transitioning) return
    busy.current = true; setPending(true)
    try { await onboardingService.save({ step: Math.max(1, step - 1), answers }); move(step - 1) }
    catch (error) { setError(error.message) }
    finally { busy.current = false; setPending(false) }
  }
  const finished = state?.status === 'completed' && !editing
  const actions = <>
    {error && <p className="form-error" role="alert">{error}</p>}
    <footer className="registration-actions">
      {!finished && step > 0 && <button className="button" type="button" disabled={pending || transitioning} onClick={back}>Anterior</button>}
      {finished ? <button type="button" className="button primary" onClick={() => journey('library-enter', null, () => navigate(state?.guide?.step === 'analysis' ? '/profile?tab=analysis' : profileDestination(params.toString())))}>Ingresar a LibrIAverse</button> : <button className="button primary" disabled={pending || transitioning || Boolean(user && !hydrated.current)}>{pending ? step === 7 ? 'Consultando Gemini…' : 'Guardando…' : step === 7 ? 'Confirmar y finalizar' : 'Siguiente'}</button>}
    </footer>{saved && <p className="registration-save-state" role="status">{saved}</p>}
  </>
  if (authLoading) return <main className="auth-page register-page"><div className="register-library-scene" aria-hidden="true" /><p className="auth-card" role="status">Recuperando tu sesión…</p></main>

  return <main className={`auth-page register-page register-page--spread${step === 7 ? ' register-page--universe' : ''}${motionEnabled ? '' : ' registration-no-motion'}`}>
    <div className="register-library-scene" aria-hidden="true" />
    <header className="registration-brand"><span aria-hidden="true">✦ <BookOpen size={32} /> ✦</span><h2>LibrIAverse</h2><p>Tu universo literario, potenciado por IA</p></header>
    <form className={`auth-card register-card registration-wizard registration-wizard--spread${step === 0 ? ' registration-wizard--account-only' : ''}${step === 7 ? ' registration-wizard--universe' : ''}`} data-step={step} data-account-created={Boolean(user)} aria-label="Registro e identidad literaria" aria-busy={pending || loading} onSubmit={submit}>
      <header className="registration-progress"><span>Paso {step + 1} de 8 · {step === 0 ? 'Tu cuenta' : 'Tu universo literario'}</span><progress max="8" value={step + 1} aria-label="Progreso del registro" /></header>
      <>
        {loading && <p role="status">Recuperando tus preferencias…</p>}
        {error && !hydrated.current && user && <div><p role="alert">{error}</p><button type="button" className="button" onClick={() => setRetry(value => value + 1)}>Reintentar</button></div>}
        <h1 ref={heading} tabIndex={-1} id="registration-heading">{headings[step]}</h1>
        <div className="registration-viewport"><div className="registration-track" data-direction={direction}>
          {headings.map((title, index) => <section key={title} className={`registration-panel${index === 0 ? ' registration-panel--account' : ''}`} inert={index === 0 ? !accountVisible : index !== question} aria-hidden={index === 0 ? !accountVisible : index !== question} aria-label={title}>
            <header className="registration-card-heading"><span>Paso {index + 1} de 8 · {index === 0 ? 'Tu cuenta' : 'Tu universo literario'}</span><progress max="8" value={index + 1} aria-label={index === 0 ? 'Progreso de tu cuenta' : 'Progreso de preferencias'} /><h2>{title}</h2><span className="registration-card-divider" aria-hidden="true">✦</span></header>
            {index === 0 && !user && <>
              <label>Nombre<input name="name" autoComplete="name" required minLength="2" maxLength="100" disabled={pending} /></label>
              <label>Correo electrónico<input name="email" type="email" autoComplete="email" required disabled={pending} /></label>
              <RegistrationPasswordFields disabled={pending} />
              <p>¿Ya tienes cuenta? <Link to={`/login?next=${encodeURIComponent(profileDestination(params.toString()))}`} onClick={event => {
                if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
                event.preventDefault()
                journey('return', null, () => navigate(`/login?next=${encodeURIComponent(profileDestination(params.toString()))}`))
              }}>Ingresa</Link></p>
            </>}
            {index === 0 && user && <><p>Tu cuenta ya está creada.</p><p>{user.display_name}</p><p>{user.email}</p><p>Continúa para configurar tu universo literario.</p></>}
            {index === 0 && step >= 5 && <FavoriteStack className="registration-favorites--desktop" ids={answers.favorite_work_ids} books={favoriteBooks} onRemove={!finished && !pending ? removeFavorite : undefined} />}
            {index === 1 && <><p>Elige entre 1 y 5 géneros.</p>{catalogError ? <p role="alert">{catalogError} <button type="button" className="button" onClick={() => setRetry(value => value + 1)}>Reintentar</button></p> : !catalogs.genres.length ? <p role="status">Cargando géneros…</p> : <PagedChoices options={catalogs.genres} selected={answers.genre_ids} pageSize={mobile ? 8 : 18} onChange={value => update('genre_ids', value)} />}</>}
            {index === 2 && <><p>Elige entre 1 y 5 elementos narrativos.</p><PagedChoices options={catalogs.tropes} selected={answers.trope_ids} noun="elementos narrativos" placeholder="Misterios, magia, personajes…" pageSize={mobile ? 8 : 15} onChange={value => update('trope_ids', value)} /></>}
            {index === 3 && <><p>Elige entre 1 y 3 emociones.</p><Choices options={state?.emotions || []} selected={answers.emotions} limit={3} onChange={value => update('emotions', value)} /></>}
            {index === 4 && <><p>Elige la opción que mejor te representa.</p><Choices options={state?.habits || []} selected={answers.habit} single onChange={value => update('habit', value)} /></>}
            {index === 5 && <div className="registration-book-picker">
              <p>Hasta cinco obras. Al finalizar, tus favoritos se añadirán a tu biblioteca como Pendiente. Puedes continuar sin elegir libros.</p>
              <label>Buscar título o autor<input type="search" value={query} onChange={event => setQuery(event.target.value)} /></label>
              <p aria-live="polite">{answers.favorite_work_ids.length} de 5 favoritos seleccionados</p>
              {searching && <p role="status">Buscando obras…</p>}{searchError && <p role="alert">{searchError}</p>}
              {!searching && query.trim() && !results.length && !searchError && <p>No hay obras disponibles para esa búsqueda.</p>}
              <div className="registration-books">{results.slice(visibleBookPage * bookResultsPerPage, (visibleBookPage + 1) * bookResultsPerPage).map(book => <button type="button" key={book.canonicalWorkId} disabled={answers.favorite_work_ids.includes(book.canonicalWorkId) || answers.favorite_work_ids.length >= 5} onClick={() => {
                setFavoriteBooks(current => ({ ...current, [book.canonicalWorkId]: { title: book.title, authors: book.authors, cover_url: book.image } }))
                update('favorite_work_ids', [...answers.favorite_work_ids, book.canonicalWorkId])
              }}>
                {book.image && <img src={book.image} alt="" />}<span><strong>{book.title}</strong><small>{[...new Set(book.authors || [book.author])].join(', ')}</small></span><span aria-hidden="true">{answers.favorite_work_ids.includes(book.canonicalWorkId) ? '✓' : '＋'}</span>
              </button>)}</div>
              {bookPageCount > 1 && <div className="registration-genre-pagination" aria-label="Páginas de obras">
                <button type="button" aria-label="Página anterior de obras" disabled={visibleBookPage === 0} onClick={() => setBookPage(visibleBookPage - 1)}>←</button>
                <span aria-live="polite">{visibleBookPage + 1} de {bookPageCount}</span>
                <button type="button" aria-label="Página siguiente de obras" disabled={visibleBookPage + 1 === bookPageCount} onClick={() => setBookPage(visibleBookPage + 1)}>→</button>
              </div>}
            </div>}
            {index === 6 && <><p>Elige cómo quieres que se vea tu experiencia en LibrIAverse. Puedes cambiarlo cuando quieras.</p>
              <div className="registration-themes" role="group" aria-label="Tema visual gratuito">{[['lavanda', 'Tema claro'], ['dark', 'Tema oscuro']].map(([id, name]) => <button type="button" key={id} className={`registration-theme-preview ${id}${answers.theme === id ? ' selected' : ''}`} aria-pressed={answers.theme === id} onClick={() => { update('theme', id); selectTheme(id) }}>
                <span className="registration-mini-ui" aria-hidden="true"><span>LibrIAverse</span><span>Mi biblioteca</span><i /><i /><i /></span><strong>{name} {answers.theme === id ? '✓' : ''}</strong><small>Gratuito</small>
              </button>)}</div>
            </>}
            {index === 7 && (finished ? <InitialLiteraryDNA initial={state} motionEnabled={motionEnabled} /> : <>
              {pending ? <div className="registration-ai-progress" role="status" aria-live="polite"><strong>Buscando tus primeras recomendaciones…</strong><p>La IA está eligiendo libros según lo que nos contaste en el cuestionario. Los resultados aparecerán aquí al terminar.</p></div> : <p>Al confirmar, la IA recomendará libros según tus respuestas y favoritos. Más adelante podrás profundizar en tu ADN literario con los análisis de tu biblioteca y de cada lectura.</p>}
              <dl><dt>Géneros</dt><dd>{catalogs.genres.filter(item => answers.genre_ids.includes(item.id)).map(item => item.name).join(', ')}</dd><dt>Emociones</dt><dd>{answers.emotions.join(', ')}</dd><dt>Hábitos</dt><dd>{answers.habit}</dd><dt>Libros favoritos</dt><dd>{answers.favorite_work_ids.length}</dd><dt>Tema</dt><dd>{answers.theme === 'dark' ? 'Oscuro' : 'Claro'}</dd></dl>
              <p>Tus afinidades iniciales serán privadas. Podrás compartirlas voluntariamente desde Sobre mí.</p>
            </>)}
            {index >= 5 && <FavoriteStack className={index === 7 ? 'registration-favorites--universe' : 'registration-favorites--mobile'} ids={answers.favorite_work_ids} books={favoriteBooks} onRemove={!finished && !pending ? removeFavorite : undefined} />}
            {index === step && <div className="registration-card-actions">{actions}</div>}
          </section>)}
        </div></div>
      </>
      {user && <button className="button text" type="button" disabled={pending} onClick={async () => { if (await logout()) navigate('/login') }}>Cerrar sesión</button>}
    </form>
    <button className="login-motion-toggle" type="button" aria-pressed={motionEnabled} onClick={() => setMotionEnabled(value => !value)}>{motionEnabled ? 'Pausar animaciones' : 'Activar animaciones'}</button>
  </main>
}
