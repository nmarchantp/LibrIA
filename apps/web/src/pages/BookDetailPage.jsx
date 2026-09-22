import { useEffect, useState } from 'react'
import { Navigate, Link, useParams } from 'react-router-dom'
import BookCover from '../components/BookCover'
import { useLibrary } from '../context/LibraryContext'
import { getGoogleBookById } from '../services/booksService'

export default function BookDetailPage() {
  const { id } = useParams()
  const { getBook, updateStatus, addBook } = useLibrary()
  const [loading, setLoading] = useState(true)
  const [detailBook, setDetailBook] = useState(null)
  const [statusError, setStatusError] = useState('')

  useEffect(() => {
    const existingBook = getBook(id)
    if (existingBook) {
      setDetailBook(existingBook)
      setLoading(false)
      return
    }

    let active = true

    const loadBook = async () => {
      try {
        const remoteBook = await getGoogleBookById(id)
        if (!active) return

        if (remoteBook) {
          addBook(remoteBook)
          setDetailBook(remoteBook)
        }
      } catch (error) {
        if (active) setDetailBook(null)
      } finally {
        if (active) setLoading(false)
      }
    }

    loadBook()
    return () => { active = false }
  }, [id, getBook, addBook])

  const book = getBook(id) ?? detailBook
  const changeStatus = async status => {
    setStatusError('')
    try { await updateStatus(book.id, status) }
    catch (cause) { setStatusError(cause.message || 'No se pudo registrar el cambio de lectura.') }
  }

  if (loading) {
    return <section className="page-width page"><div className="modal detail-page"><p>Cargando información del libro…</p></div></section>
  }

  if (!book) return <Navigate to="/books" replace />

  return (
    <section className="page-width page">
      <div className="modal detail-page">
        <BookCover book={book} large />
        <div className="modal-copy">
          <span className="kicker">{book.status ?? 'Sin estado'}</span>
          <h1 className="page-title">{book.title}</h1>
          <p className="author">{book.author} · {book.year ?? book.publishedDate}</p>

          {(book.averageRating || book.ratingsCount) && (
            <p style={{ marginTop: '8px', color: '#8a6a2a', fontWeight: 700 }}>
              ★ {book.averageRating ?? 'Sin calificación'}
              {book.ratingsCount ? ` · ${book.ratingsCount} valoraciones` : ''}
            </p>
          )}

          <div
            style={{ lineHeight: 1.7, color: '#59645f', marginTop: '18px' }}
            dangerouslySetInnerHTML={{
              __html: book.description || 'Este libro no tiene descripción disponible en Google Books.'
            }}
          />

          <div style={{ display: 'grid', gap: '8px', marginTop: '18px', fontSize: '14px', color: '#59645f' }}>
            {book.subtitle && <div><strong>Subtítulo:</strong> {book.subtitle}</div>}
            {book.publisher && <div><strong>Editorial:</strong> {book.publisher}</div>}
            {book.pageCount && <div><strong>Páginas:</strong> {book.pageCount}</div>}
            {book.language && <div><strong>Idioma:</strong> {book.language}</div>}
            {book.categories?.length > 0 && <div><strong>Categorías:</strong> {book.categories.join(', ')}</div>}
            {book.printType && <div><strong>Tipo:</strong> {book.printType}</div>}
            {book.maturityRating && <div><strong>Clasificación:</strong> {book.maturityRating}</div>}
            {(book.previewLink || book.infoLink || book.canonicalVolumeLink) && (
              <div>
                <strong>Más información:</strong>{' '}
                {book.previewLink && <a href={book.previewLink} target="_blank" rel="noreferrer">Vista previa</a>}
                {book.infoLink && (
                  <>
                    {' · '}
                    <a href={book.infoLink} target="_blank" rel="noreferrer">Google Books</a>
                  </>
                )}
                {book.canonicalVolumeLink && (
                  <>
                    {' · '}
                    <a href={book.canonicalVolumeLink} target="_blank" rel="noreferrer">Volumen</a>
                  </>
                )}
              </div>
            )}
          </div>

          <label>
            Estado
            <select value={book.status ?? ''} onChange={e => changeStatus(e.target.value)}>
              <option value="">Sin estado</option>
              <option>Leyendo</option>
              <option>Pendiente</option>
              <option>Terminado</option>
              <option disabled>Abandonado</option>
            </select>
          </label>
          {statusError && <p className="notice" role="alert">{statusError}</p>}

          <Link className="button primary" to={`/reading/${book.id}`}>Reseñar o registrar avance</Link>
        </div>
      </div>
    </section>
  )
}
