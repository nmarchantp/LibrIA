import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiRequest, apiAssetUrl } from '../api/client'
import BookCover from './BookCover'
import ProfileEvents from './ProfileEvents'
import PublicLiteraryDNA from './PublicLiteraryDNA'
import ProfileReadingStats from './ProfileReadingStats'
import ReaderEssence from './ReaderEssence'
import DnaProfileSections from './DnaProfileSections'
import './ProfileShowcase.css'
import './ReaderDna.css'

const labels = { library: 'Mi biblioteca', activity: 'Mi actividad', analyses: 'Mis análisis' }
const statuses = { pending: 'Pendiente', reading: 'Leyendo', finished: 'Terminado', abandoned: 'Abandonado' }

function SharedSection({ profileId, section, preview, active }) {
  const [state, setState] = useState({ items: [], loading: true })
  const [offset, setOffset] = useState(0)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => { if (active) setOffset(0) }, [active])
  useEffect(() => {
    if (!active) return
    const controller = new AbortController()
    setState(current => ({ ...current, loading: true, error: '' }))
    apiRequest(`/profiles/${profileId}/showcase/${section}?preview=${preview}&offset=${offset}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` }, signal: controller.signal,
    }).then(result => {
      if (!controller.signal.aborted) setState(current => ({ ...result, loading: false, items: offset ? [...current.items, ...(result.items || [])] : result.items || [] }))
    }).catch(cause => {
      if (!controller.signal.aborted) setState(current => ({ ...current, loading: false, error: cause.status === 403 ? 'Esta sección ya no está disponible.' : 'No se pudo cargar esta sección.' }))
    })
    return () => controller.abort()
  }, [profileId, section, preview, offset, attempt, active])
  return <section className="reader-personal-card profile-showcase-section" aria-label={labels[section]}>
    <h2>{labels[section]}</h2>
    {state.loading && <p role="status">Cargando…</p>}
    {state.error && <div role="alert"><p>{state.error}</p><button className="button" type="button" onClick={() => setAttempt(value => value + 1)}>Reintentar</button></div>}
    {!state.error && <>
      {section === 'library' && <>
        {state.total !== undefined && <p>{state.total} libros en la biblioteca</p>}
        <ProfileReadingStats counts={state.counts} loading={state.loading} />
        <div className="profile-showcase-books">{state.items.map(book => <article key={book.id}>
          <Link to={`/books/${encodeURIComponent(book.id)}`}><BookCover book={{ title: book.title, author: book.authors.join(', '), image: apiAssetUrl(book.cover_url), initial: book.title?.[0] }} /><h3>{book.title}</h3></Link>
          <p>{book.authors.join(', ')}</p><span>{statuses[book.status]}</span>
        </article>)}</div>
      </>}
      {section === 'activity' && <div className="profile-showcase-activity">{state.items.map(item => <article key={item.id}>
        <span>{item.publication_type === 'theory' ? 'Teoría' : 'Nota'}</span><h3>{item.title}</h3><p className="profile-showcase-body">{item.body}</p>{item.book_title && <small>{item.book_title}</small>}
        <Link to={`/?publication=${item.id}`}>Ver publicación</Link>
      </article>)}</div>}
      {!state.loading && section !== 'analyses' && !state.items.length && <p>Aún no hay contenido en esta sección.</p>}
      {section === 'analyses' && <>
        <PublicLiteraryDNA profileId={profileId} preview={preview} />
        {state.profile && Object.keys(state.profile).length > 0 ? <>
          {state.profile.reader_essence && <ReaderEssence essence={state.profile.reader_essence} />}
          {state.profile.interpretation && <p>{state.profile.interpretation}</p>}
          <DnaProfileSections content={state.profile} />
        </> : !state.loading && <p>Aún no hay un análisis lector disponible.</p>}
        {state.recommendations?.length > 0 && <><h3>Recomendaciones de lectura</h3><div className="profile-showcase-books">{state.recommendations.map((book, index) => <article key={book.work_id || index}>
          <Link to={`/books/${encodeURIComponent(book.work_id)}`}><BookCover book={{ title: book.title, image: apiAssetUrl(book.cover_url), initial: book.title?.[0] }} /><h3>{book.title}</h3></Link><p>{book.explanation}</p>
        </article>)}</div></>}
      </>}
      {state.has_more && <button className="button" type="button" disabled={state.loading} onClick={() => setOffset(state.items.length)}>Ver más</button>}
    </>}
  </section>
}

export default function ProfileShowcase({ profileId, sections = [], preview = false, active = true }) {
  if (!profileId) return null
  return <div className="profile-showcase">
    {['library', 'activity', 'events', 'analyses'].filter(section => sections.includes(section)).map(section => section === 'events'
      ? <section className="reader-personal-card profile-showcase-section" key={section}><ProfileEvents profileId={profileId} preview={preview} readOnly active={active} /></section>
      : <SharedSection key={`${profileId}:${section}:${preview}`} profileId={profileId} section={section} preview={preview} active={active} />)}
  </div>
}
