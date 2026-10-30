import BookCategoryChips from '../components/BookCategoryChips'
import { normalizeBookCategories } from '../components/bookCategories'
import BookSynopsisModal from '../components/BookSynopsisModal'
import { parseBookSynopsis } from '../components/bookSynopsis'
import RatingStar from '../components/RatingStar'
import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowUpRight, Ban, Barcode, BookOpen, CalendarDays, Check, ChevronDown, ChevronLeft, ChevronRight, CircleCheck, CircleSlash2, Clock3, FileText, Globe2, Landmark, UserRound, Users } from 'lucide-react'
import { Navigate, Link, useParams } from 'react-router-dom'
import BookCover from '../components/BookCover'
import { apiAssetUrl } from '../api/client'
import BookReviews from '../components/BookReviews'
import { useLibrary } from '../context/LibraryContext'
import { getGoogleBookById } from '../services/booksService'
import './BookDetailPage.css'

const languageNames = { es: 'Español', en: 'Inglés', fr: 'Francés', pt: 'Portugués' }
const formatNames = { BOOK: 'Libro', MAGAZINE: 'Revista' }

function RatingStars({ value }) {
  const rating = Number(value) || 0
  return <span className="detail-rating-stars" role="img" aria-label={`${rating} de 5 estrellas`}>
    {[1, 2, 3, 4, 5].map(star => <span className="detail-rating-star" key={star}>
      <RatingStar />
      <span style={{ width: `${Math.max(0, Math.min(1, rating - star + 1)) * 100}%` }}><RatingStar selected /></span>
    </span>)}
  </span>
}

function ReaderAvatar({ reader }) {
  const initials = (reader.displayName || 'L').split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase()
  return reader.avatarUrl
    ? <img src={apiAssetUrl(reader.avatarUrl)} alt={reader.displayName} title={reader.displayName} />
    : <span title={reader.displayName} aria-label={reader.displayName}>{initials}</span>
}

export default function BookDetailPage() {
  const { id } = useParams()
  const editionsRef = useRef(null)
  const { getBook, addBook, selectReadingEdition } = useLibrary()
  const [loading, setLoading] = useState(true)
  const [detailBook, setDetailBook] = useState(null)
  const [statusError, setStatusError] = useState('')
  const [adding, setAdding] = useState(false)
  const [synopsisOpen, setSynopsisOpen] = useState(false)

  useEffect(() => {
    const existingBook = getBook(id)
    let active = true
    let request = 0
    const refresh = () => {
      const current = ++request
      getGoogleBookById(id).then(remoteBook => {
        if (active && current === request && remoteBook) setDetailBook(remoteBook)
      }).catch(() => {
        if (active && current === request) setDetailBook(previous =>
          previous && [previous.id, previous.workId, previous.externalId, previous.rawVolume?.id].includes(id)
            ? previous : existingBook || null)
      }).finally(() => {
        if (active && current === request) setLoading(false)
      })
    }
    const onVisible = () => { if (document.visibilityState === 'visible') refresh() }
    refresh()
    window.addEventListener('libria:book-activity-changed', refresh)
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      active = false
      window.removeEventListener('libria:book-activity-changed', refresh)
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [id, getBook])

  const libraryBook = getBook(id)
  const book = detailBook ? {
    ...libraryBook, ...detailBook,
    ...(libraryBook ? {
      status: libraryBook.status, progress: libraryBook.progress, readingId: libraryBook.readingId,
      workId: libraryBook.workId, editionId: detailBook.editionId || libraryBook.editionId,
    } : {}),
  } : libraryBook

  const synopsis = useMemo(() => parseBookSynopsis(book?.description), [book?.description])

  const selectEdition = editionId => {
    const edition = detailBook?.editions?.find(item => item.id === editionId)
    if (!edition) return
    setDetailBook(current => ({
      ...current, editionId: edition.id, editionExplicit: true, externalId: edition.externalId,
      title: edition.title || current.title, originalTitle: edition.originalTitle || edition.title || current.originalTitle,
      language: edition.language || current.language,
      publisher: edition.publisher || 'Editorial desconocida', publishedDate: edition.publishedDate || '',
      pageCount: edition.pageCount || null, printType: edition.format || '',
      isbn: edition.isbn13 || edition.isbn10 || '', image: edition.coverUrl || null,
    }))
  }

  const addToLibrary = async () => {
    setStatusError('')
    setAdding(true)
    try { await addBook(book) }
    catch (cause) { setStatusError(cause.message || 'No se pudo agregar el libro.') }
    finally { setAdding(false) }
  }

  const saveEdition = async () => {
    setAdding(true); setStatusError('')
    try { await selectReadingEdition(libraryBook, detailBook.editionId) }
    catch (cause) { setStatusError(cause.message || 'No se pudo seleccionar la edición.') }
    finally { setAdding(false) }
  }

  if (loading) return <section className="page-width page"><div className="detail-loading" role="status">Cargando información del libro…</div></section>
  if (!book) return <Navigate to="/books" replace />
  if (detailBook?.workId && /^[0-9a-f-]{36}$/i.test(id) && detailBook.workId!==id && !detailBook.editionExplicit)
    return <Navigate to={`/books/${detailBook.workId}`} replace />

  const editions = book.editions ?? []
  const stats = book.readingStats ?? { finished: 0, reading: 0, abandoned: 0, readerPreview: [] }
  const rating = Number(book.averageRating) || 0
  const ratingsCount = Number(book.ratingsCount) || 0
  const firstAuthor = book.authors?.[0] || book.author
  const details = [
    ['Editorial', book.publisher, Landmark], ['Publicación', book.publishedDate, CalendarDays],
    ['Páginas', book.pageCount ? `${book.pageCount} páginas` : null, FileText],
    ['Idioma', languageNames[book.language] || book.language?.toUpperCase(), Globe2],
    ['Formato', formatNames[book.printType] || book.printType, BookOpen], ['ISBN', book.isbn, Barcode],
  ]

  const statusClass = { Terminado: 'finished', Leyendo: 'reading', Pendiente: 'pending', Abandonado: 'abandoned' }[book.status]
  const StatusIcon = { Terminado: Check, Leyendo: BookOpen, Pendiente: Clock3, Abandonado: CircleSlash2 }[book.status] || BookOpen
  const formattedRating = rating.toLocaleString('es-CL', { maximumFractionDigits: 2 })
  const catalogCategories = book.rawVolume?.volumeInfo?.categories
  const categories = normalizeBookCategories(catalogCategories?.length ? catalogCategories : (book.categories || []), book.tropes || [])

  return <section className="page-width page book-detail-page">
    <article className="detail-hero">
      <div className="detail-cover-wrap"><BookCover book={book} large />
        <Link className="detail-author-link" to={`/books?by=author&q=${encodeURIComponent(firstAuthor || '')}`} aria-label="Ver más del mismo autor" title="Ver más del mismo autor"><UserRound aria-hidden="true" /><span>Más del autor</span><ArrowUpRight aria-hidden="true" /></Link>
      </div>
      <div className="detail-intro">
        <div className="detail-intro-copy">
        <BookCategoryChips key={book.id} categories={categories} />
        <h1>{book.title}</h1>
        {book.subtitle && <p className="detail-subtitle">{book.subtitle}</p>}
        <p className="detail-byline"><span>{book.author || 'Autor no disponible'}</span>{book.year && <span className="detail-publication-year"> · {book.year}</span>}
        {libraryBook && statusClass && <span className={`detail-reading-status ${statusClass}`}><StatusIcon size={14} aria-hidden="true" />{book.status}</span>}
        </p>
        <div className="detail-synopsis-preview">{synopsis.text || 'Este libro no tiene una sinopsis disponible.'}</div>
        {synopsis.text && <button className="detail-synopsis-more" type="button" onClick={() => setSynopsisOpen(true)}>Ver más<ChevronDown size={17} aria-hidden="true" /></button>}
        </div>
    <div className="detail-intro-footer">
    <div className="detail-actions">
      {libraryBook?.readingId
        ? <Link className="detail-library-action" to={`/library/${encodeURIComponent(book.id)}`}><span className="detail-action-surface"><BookOpen aria-hidden="true" />Ver en mi biblioteca<ArrowUpRight aria-hidden="true" /></span></Link>
        : <button className="detail-library-action" type="button" onClick={addToLibrary} disabled={adding || (book.catalogFlow === 'discovery-v1' && !book.editionId && !book.selectionReference && !(book.editionOptional && book.workId))}><span className="detail-action-surface"><BookOpen aria-hidden="true" />{adding ? 'Agregando…' : book.editionOptional && !book.editionExplicit ? 'Agregar obra sin edición' : book.catalogFlow === 'discovery-v1' ? 'Agregar esta edición' : 'Agregar a biblioteca'}<ArrowUpRight aria-hidden="true" /></span></button>}
        {libraryBook?.editionOptional && !libraryBook.editionId && detailBook?.editionExplicit && <button type="button" className="button secondary" disabled={adding} onClick={saveEdition}>Seleccionar esta edición para mi lectura</button>}

    </div>
    {statusError && <p className="detail-error" role="alert">{statusError}</p>}
    </div>

      </div>
      <aside className="detail-community" aria-labelledby="rating-title">
        <h2 id="rating-title"><Users size={19} aria-hidden="true" />VALORACIÓN DE LA COMUNIDAD</h2>
        <div className="rating-line"><RatingStars value={rating} /><strong>{formattedRating}<small> / 5</small></strong></div>
        <p className="detail-rating-count">{ratingsCount.toLocaleString('es-CL')} {ratingsCount === 1 ? 'valoración' : 'valoraciones'}</p>
        <div className="reader-counts">
          <div className="reader-count-finished"><CircleCheck aria-hidden="true" /><strong>{Number(stats.finished ?? 0).toLocaleString('es-CL')}</strong><span>Lo leyeron</span></div>
          <div><BookOpen aria-hidden="true" /><strong>{Number(stats.reading ?? 0).toLocaleString('es-CL')}</strong><span>Leyendo</span></div>
          <div className="reader-count-abandoned"><Ban aria-hidden="true" /><strong>{Number(stats.abandoned ?? 0).toLocaleString('es-CL')}</strong><span>Abandonaron</span></div>
        </div>
        {stats.readerPreview?.length > 0 && <div className="reader-avatars" aria-label="Lectores que terminaron este libro">{stats.readerPreview.map((reader, index) => <ReaderAvatar reader={reader} key={`${reader.displayName}-${index}`} />)}</div>}
      </aside>
      <dl className="book-data-grid" aria-label="Ficha técnica">{details.map(([label, value, Icon]) => <div key={label}><Icon aria-hidden="true" /><dt>{label}</dt><dd>{value || 'No disponible'}</dd></div>)}</dl>
    </article>
    {synopsisOpen && <BookSynopsisModal title={book.title} onClose={() => setSynopsisOpen(false)}>{synopsis.content}</BookSynopsisModal>}

    {editions.length > 0 && <section className="detail-section editions-section" aria-labelledby="editions-title">
      <div className="detail-section-heading">
        <div><span className="kicker">OTRAS VERSIONES</span><h2 id="editions-title">Ediciones</h2></div>
        {editions.length > 3 && <div className="carousel-controls">
          <button type="button" aria-label="Ver ediciones anteriores" onClick={() => editionsRef.current?.scrollBy({ left: -240, behavior: 'smooth' })}><ChevronLeft /></button>
          <button type="button" aria-label="Ver más ediciones" onClick={() => editionsRef.current?.scrollBy({ left: 240, behavior: 'smooth' })}><ChevronRight /></button>
        </div>}
      </div>
      <div className="edition-carousel" ref={editionsRef}>
        {editions.map(edition => {
          const editionCover = { ...book, title: edition.title || book.title, image: edition.coverUrl || null }
          return <button type="button" className={`edition-card ${book.editionId === edition.id ? 'active' : ''}`} key={edition.id}
            aria-pressed={book.editionId === edition.id} onClick={() => selectEdition(edition.id)}>
            <BookCover book={editionCover} />
            <span><strong>{edition.publisher || 'Editorial desconocida'}</strong><small>{edition.publishedDate || 'Fecha no informada'} · {(edition.language || '—').toUpperCase()}</small></span>
          </button>
        })}
      </div>
    </section>}

    <BookReviews key={id} bookRef={id} />
  </section>
}
