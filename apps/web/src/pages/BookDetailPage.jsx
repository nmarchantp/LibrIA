import RatingStar from '../components/RatingStar'
import { useEffect, useRef, useState } from 'react'
import { BookOpen, ChevronLeft, ChevronRight, CircleSlash2, Users } from 'lucide-react'
import { Navigate, Link, useParams } from 'react-router-dom'
import BookCover from '../components/BookCover'
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
    ? <img src={reader.avatarUrl} alt={reader.displayName} title={reader.displayName} />
    : <span title={reader.displayName} aria-label={reader.displayName}>{initials}</span>
}

export default function BookDetailPage() {
  const { id } = useParams()
  const editionsRef = useRef(null)
  const { getBook, addBook } = useLibrary()
  const [loading, setLoading] = useState(true)
  const [detailBook, setDetailBook] = useState(null)
  const [statusError, setStatusError] = useState('')
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    const existingBook = getBook(id)
    if (existingBook && !existingBook.rawVolume && (String(id).includes(':') || /^\d+$/.test(id))) {
      setDetailBook(existingBook)
      setLoading(false)
      return
    }
    let active = true
    getGoogleBookById(id).then(remoteBook => {
      if (active && remoteBook) setDetailBook(remoteBook)
    }).catch(() => {
      if (active) setDetailBook(existingBook || null)
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [id, getBook])

  const libraryBook = getBook(id)
  const book = detailBook ? {
    ...libraryBook, ...detailBook,
    ...(libraryBook ? {
      status: libraryBook.status, progress: libraryBook.progress, readingId: libraryBook.readingId,
      workId: libraryBook.workId, editionId: detailBook.editionId || libraryBook.editionId,
    } : {}),
  } : libraryBook

  const selectEdition = editionId => {
    const edition = detailBook?.editions?.find(item => item.id === editionId)
    if (!edition) return
    setDetailBook(current => ({
      ...current, editionId: edition.id, externalId: edition.externalId,
      title: edition.title || current.title, language: edition.language || current.language,
      publisher: edition.publisher || 'Editorial desconocida', publishedDate: edition.publishedDate || '',
      pageCount: edition.pageCount || null, printType: edition.format || 'BOOK',
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

  if (loading) return <section className="page-width page"><div className="detail-loading" role="status">Cargando información del libro…</div></section>
  if (!book) return <Navigate to="/books" replace />

  const editions = book.editions ?? []
  const stats = book.readingStats ?? { finished: 0, reading: 0, abandoned: 0, readerPreview: [] }
  const rating = Number(book.averageRating) || 0
  const ratingsCount = Number(book.ratingsCount) || 0
  const firstAuthor = book.authors?.[0] || book.author
  const details = [
    ['Editorial', book.publisher], ['Publicación', book.publishedDate || book.year],
    ['Páginas', book.pageCount ? `${book.pageCount} páginas` : null],
    ['Idioma', languageNames[book.language] || book.language?.toUpperCase()],
    ['Formato', formatNames[book.printType] || book.printType], ['ISBN', book.isbn],
  ]

  return <section className="page-width page book-detail-page">
    <article className="detail-hero">
      <div className="detail-cover-wrap"><BookCover book={book} large /></div>
      <div className="detail-intro">
        <span className="kicker">{book.status || 'DETALLE DEL LIBRO'}</span>
        <h1>{book.title}</h1>
        {book.subtitle && <p className="detail-subtitle">{book.subtitle}</p>}
        <p className="detail-byline"><strong>{book.author}</strong> · {book.year || book.publishedDate || 'Año no informado'}</p>
        <div className="detail-actions">
          {libraryBook?.readingId
            ? <Link className="button primary" to={`/library/${encodeURIComponent(book.id)}`}><BookOpen aria-hidden="true" />Ver en mi biblioteca</Link>
            : <button className="button primary" type="button" onClick={addToLibrary} disabled={adding}>
              <BookOpen aria-hidden="true" />{adding ? 'Agregando…' : 'Agregar a biblioteca'}
            </button>}
          <Link className="button detail-secondary" to={`/books?by=author&q=${encodeURIComponent(firstAuthor)}`}>Ver más del mismo autor</Link>
        </div>
        {statusError && <p className="detail-error" role="alert">{statusError}</p>}
      </div>
    </article>

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

    <section className="detail-section detail-social" aria-labelledby="rating-title">
      <div className="detail-rating">
        <span className="kicker">COMUNIDAD</span><h2 id="rating-title">Valoración del libro</h2>
        <div className="rating-line"><strong>{rating ? rating.toFixed(1) : '0'} / 5</strong><RatingStars value={rating} /></div>
        <p>{ratingsCount.toLocaleString('es-CL')} {ratingsCount === 1 ? 'valoración' : 'valoraciones'}</p>
      </div>
      <div className="reader-summary-block">
        <div className="reader-avatars" aria-label="Lectores que terminaron este libro">
          {stats.readerPreview?.map((reader, index) => <ReaderAvatar reader={reader} key={`${reader.displayName}-${index}`} />)}
          {!stats.readerPreview?.length && <span className="reader-avatar-empty"><Users aria-hidden="true" /></span>}
        </div>
        <div className="reader-counts">
          <div><BookOpen aria-hidden="true" /><strong>{stats.finished}</strong><span>lo leyeron</span></div>
          <div><Users aria-hidden="true" /><strong>{stats.reading}</strong><span>leyendo</span></div>
          <div><CircleSlash2 aria-hidden="true" /><strong>{stats.abandoned}</strong><span>lo abandonaron</span></div>
        </div>
      </div>
    </section>

    <BookReviews key={id} bookRef={id} />

    <section className="detail-section" aria-labelledby="book-data-title">
      <span className="kicker">FICHA TÉCNICA</span><h2 id="book-data-title">Detalle del libro</h2>
      <dl className="book-data-grid">{details.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || 'No informado'}</dd></div>)}</dl>
    </section>

    <section className="detail-section synopsis-section" aria-labelledby="synopsis-title">
      <span className="kicker">SOBRE EL LIBRO</span><h2 id="synopsis-title">Sinopsis</h2>
      <div className="synopsis-copy">{book.description || 'Este libro no tiene una sinopsis disponible.'}</div>
      <div className="genre-tags" aria-label="Géneros del libro">
        {(book.categories?.length ? book.categories : ['Sin género informado']).map(category => <span key={category}>{category}</span>)}
      </div>
    </section>
  </section>
}
