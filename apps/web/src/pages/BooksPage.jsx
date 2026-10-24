import RatingStar from '../components/RatingStar'
import { CalendarDays, ChevronRight, Cloud, Database, FileText, Search, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import BookCover from '../components/BookCover'
import { searchBookCatalog } from '../services/booksService'

const searchModes = [['title', 'Título'], ['author', 'Autor'], ['isbn', 'ISBN']]

export default function BooksPage() {
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState(searchParams.get('q') ?? '')
  const [searchBy, setSearchBy] = useState(searchParams.get('by') ?? 'title')
  const [books, setBooks] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [retry, setRetry] = useState(0)
  const [startIndex, setStartIndex] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [nextStartIndex, setNextStartIndex] = useState(0)
  const [cursor, setCursor] = useState({ provider: 'google_books', page: 1, append: false })
  const [nextCursor, setNextCursor] = useState({ provider: 'google_books', page: 1 })

  useEffect(() => {
    let active = true
    const controller = new AbortController()
    const loadBooks = async () => {
      if (!query.trim()) {
        setBooks([]); setError(''); setWarning(''); setLoading(false); setHasMore(false)
        return
      }
      try {
        setLoading(true); setError(''); setWarning('')
        const results = await searchBookCatalog(query, searchBy, { signal: controller.signal, refresh: retry > 0, startIndex, ...cursor })
        if (active) {
          setBooks(current => cursor.append ? [...new Map([...current, ...results.books].map(book => [book.id, book])).values()] : results.books)
          setWarning(results.warning); setHasMore(results.hasMore); setNextStartIndex(results.nextStartIndex)
          setNextCursor({ provider: results.provider, page: results.nextPage, append: true })
        }
      } catch (cause) {
        if (active && cause.name !== 'AbortError') {
          if (!cursor.append) setBooks([])
          setError(cause.code === 'backend_connection' ? cause.message : cause.message || 'No se pudo consultar el catálogo. Inténtalo nuevamente.')
        }
      } finally {
        if (active) setLoading(false)
      }
    }
    const timer = setTimeout(loadBooks, 350)
    return () => { active = false; clearTimeout(timer); controller.abort() }
  }, [query, searchBy, retry, startIndex, cursor])

  return (
    <section className="page-width page books-search-page">
      <span className="kicker">AÑADIR LIBRO</span>
      <h1 className="page-title">Busca tu próxima lectura</h1>
      <p className="page-lead">Encuentra la obra por título, autor o ISBN y selecciona el resultado correcto.</p>

      <div className="catalog-search-controls">
        <label className="search-box catalog-search-input">
          <Search aria-hidden="true" />
          <input type="search" aria-label={`Buscar por ${searchBy}`} autoComplete="off"
            value={query} onChange={event => { setQuery(event.target.value); setStartIndex(0); setRetry(0); setHasMore(false); setCursor({ provider: 'google_books', page: 1, append: false }) }}
            placeholder={searchBy === 'isbn' ? 'Escribe el ISBN…' : `Buscar por ${searchBy === 'title' ? 'título' : 'autor'}…`} />
          {query && <button type="button" className="search-clear" aria-label="Limpiar búsqueda" onClick={() => setQuery('')}><X /></button>}
        </label>
        <div className="catalog-search-tabs" role="tablist" aria-label="Tipo de búsqueda">
          {searchModes.map(([value, label]) => <button type="button" role="tab" key={value}
            aria-selected={searchBy === value} className={searchBy === value ? 'active' : ''}
            onClick={() => { setSearchBy(value); setStartIndex(0); setRetry(0); setHasMore(false); setCursor({ provider: 'google_books', page: 1, append: false }) }}>{label}</button>)}
        </div>
      </div>

      <div className="catalog-results-heading" role="status" aria-live="polite">
        <strong>{loading ? 'Buscando…' : query.trim() ? `${books.length} resultados` : 'Escribe para buscar'}</strong>
        {books.length > 0 && <span>Publicación · Solo español</span>}
      </div>

      {(error || warning) && <div className="catalog-state" role="alert"><p>{error || warning}</p><button type="button" className="button primary" disabled={loading} onClick={() => setRetry(value => value + 1)}>Reintentar búsqueda</button></div>}
      {!error && !warning && !loading && query.trim() && books.length === 0 && <div className="catalog-state"><Search size={28} /><h2>No encontramos libros</h2><p>Prueba con otro criterio o revisa la escritura.</p></div>}

      <div className="catalog-result-list" aria-busy={loading}>
        {books.map(book => <Link className="catalog-result-card" to={`/books/${book.id}`} key={book.id}>
          <BookCover book={book} />
          <div className="catalog-result-copy">
            <h2>{book.title}</h2>
            {book.subtitle && <p className="catalog-result-subtitle">{book.subtitle}</p>}
            <p className="catalog-result-author">{book.author}</p>
            <div className="catalog-result-meta">
              {book.year && <span><CalendarDays />{book.year}</span>}
              {book.pageCount && <span><FileText />{book.pageCount} pág.</span>}
              {book.language && <span className="language-chip">{book.language.toUpperCase()}</span>}
              <span className={`origin-chip ${book.catalogOrigin === 'libria' ? 'origin-libria' : 'origin-google'}`}>
                {book.catalogOrigin === 'libria' ? <Database /> : <Cloud />}
                {book.catalogOrigin === 'libria' ? 'LibrIAverse' : 'Google Books'}
              </span>
              {book.editionCount > 0 && <span>{book.editionCount} {book.editionCount === 1 ? 'edición' : 'ediciones'}</span>}
              {book.averageRating && <span className="rating-chip"><RatingStar selected />{book.averageRating}{book.ratingsCount ? ` · ${book.ratingsCount.toLocaleString('es-CL')}` : ''}</span>}
            </div>
          </div>
          <ChevronRight className="catalog-result-arrow" aria-hidden="true" />
        </Link>)}
      </div>
      {hasMore && !error && !warning && <div className="catalog-state"><button type="button" className="button primary" disabled={loading} onClick={() => { setStartIndex(nextStartIndex); setCursor(nextCursor); setRetry(value => value + 1) }}>Ver más resultados</button></div>}
    </section>
  )
}
