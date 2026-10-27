import RatingStar from '../components/RatingStar'
import { ArrowUpRight, BookOpen, ChevronRight, Cloud, Database, FileText, LayoutGrid, List, Search, TrendingUp, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import BookCover from '../components/BookCover'
import { searchBookCatalog } from '../services/booksService'
import './BooksPage.css'

const searchModes = [['title', 'Título'], ['author', 'Autor'], ['isbn', 'ISBN']]
const placeholders = { title: 'Escribe el título del libro (ej: Harry Potter, Coraline…)', author: 'Escribe el nombre del autor (ej: Isabel Allende…)', isbn: 'Escribe el ISBN (ej: 9788478884452)' }
// Suggestions only use the search modes the catalog supports (title and author).
const suggestions = [['Harry Potter', 'Harry Potter', 'title'], ['Cien años de soledad', 'Cien años de soledad', 'title'], ['Obras de Neil Gaiman', 'Neil Gaiman', 'author'], ['Obras de Isabel Allende', 'Isabel Allende', 'author']]
const origins = [['all', 'Todo'], ['libria', 'LibrIAverse'], ['google', 'Google Books']]
const viewStorageKey = 'libria_books_view'
const readView = () => { try { return localStorage.getItem(viewStorageKey) === 'grid' ? 'grid' : 'list' } catch { return 'list' } }
const originOf = book => book.catalogOrigin === 'libria' ? 'libria' : 'google'

function ResultCard({ book }) {
  return <Link className="catalog-result-card" to={`/books/${book.id}`}>
    <span className="catalog-cover">
      <BookCover book={book} />
      {book.language && <span className="catalog-cover-language">{book.language.toUpperCase()}</span>}
      {book.year && <span className="catalog-cover-year">{book.year}</span>}
    </span>
    <span className="catalog-result-copy">
      <h2>{book.title}</h2>
      {book.subtitle && <span className="catalog-result-subtitle">{book.subtitle}</span>}
      <span className="catalog-result-author">{book.author}</span>
      <span className="catalog-result-meta">
        {book.pageCount && <span className="meta-chip"><FileText aria-hidden="true" />{book.pageCount} pág.</span>}
        {book.language && <span className="meta-chip language-chip">{book.language.toUpperCase()}</span>}
        <span className={`meta-chip origin-chip origin-${originOf(book)}`}>
          {originOf(book) === 'libria' ? <Database aria-hidden="true" /> : <Cloud aria-hidden="true" />}
          {originOf(book) === 'libria' ? 'LibrIAverse' : 'Google Books'}
        </span>
        {book.editionCount > 0 && <span className="meta-plain">{book.editionCount} {book.editionCount === 1 ? 'edición' : 'ediciones'}</span>}
        {book.averageRating && <span className="rating-chip" aria-label={`Valoración promedio ${book.averageRating}${book.ratingsCount ? `, ${book.ratingsCount} valoraciones` : ''}`}><RatingStar selected />{book.averageRating}{book.ratingsCount ? <small> · {book.ratingsCount.toLocaleString('es-CL')}</small> : null}</span>}
      </span>
    </span>
    <ChevronRight className="catalog-result-arrow" aria-hidden="true" />
  </Link>
}

export default function BooksPage() {
  const [searchParams] = useSearchParams()
  const inputRef = useRef(null)
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
  const [origin, setOrigin] = useState('all')
  const [view, setView] = useState(readView)

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

  const resetPaging = () => { setStartIndex(0); setRetry(0); setHasMore(false); setOrigin('all'); setCursor({ provider: 'google_books', page: 1, append: false }) }
  const search = (value, by = searchBy) => { setQuery(value); setSearchBy(by); resetPaging() }
  const changeView = value => { setView(value); try { localStorage.setItem(viewStorageKey, value) } catch { /* Only a convenience. */ } }
  const counts = { all: books.length, libria: books.filter(book => originOf(book) === 'libria').length, google: books.filter(book => originOf(book) === 'google').length }
  const activeOrigin = counts[origin] ? origin : 'all'
  const visible = activeOrigin === 'all' ? books : books.filter(book => originOf(book) === activeOrigin)
  const searching = Boolean(query.trim())

  return (
    <section className="page-width page books-search-page">
      <span className="books-kicker">Añadir libro</span>
      <h1 className="books-title">Busca tu próxima lectura</h1>
      <p className="books-lead">Encuentra la obra por título, autor o ISBN y selecciona el resultado correcto.</p>

      <div className="catalog-search-panel">
        <form className="catalog-search-input" role="search" onSubmit={event => { event.preventDefault(); inputRef.current?.blur() }}>
          <Search className="catalog-search-icon" aria-hidden="true" />
          <input ref={inputRef} type="search" aria-label={`Buscar por ${searchModes.find(([value]) => value === searchBy)?.[1].toLowerCase() || 'título'}`} autoComplete="off"
            value={query} onChange={event => { setQuery(event.target.value); resetPaging() }} placeholder={placeholders[searchBy] || placeholders.title} />
          {query && <button type="button" className="search-clear" aria-label="Limpiar búsqueda" onClick={() => { setQuery(''); inputRef.current?.focus() }}><X /></button>}
          <span className="catalog-search-divider" aria-hidden="true" />
          <button type="submit" className="catalog-search-submit" aria-label="Buscar"><ArrowUpRight /></button>
        </form>
        <div className="catalog-search-tabs" role="tablist" aria-label="Tipo de búsqueda">
          {searchModes.map(([value, label]) => <button type="button" role="tab" key={value}
            aria-selected={searchBy === value} className={searchBy === value ? 'active' : ''}
            onClick={() => { setSearchBy(value); resetPaging() }}>{label}</button>)}
        </div>
        <div className="catalog-suggestions">
          <span><TrendingUp aria-hidden="true" />Sugerencias:</span>
          <ul>{suggestions.map(([label, value, by]) => <li key={label}><button type="button" onClick={() => search(value, by)}>{label}</button></li>)}</ul>
        </div>
      </div>

      <div className="catalog-toolbar">
        <div className="catalog-results-heading" role="status" aria-live="polite">
          <strong>{loading && !books.length ? 'Buscando…' : `${visible.length} ${visible.length === 1 ? 'resultado' : 'resultados'}`}</strong>
        </div>
        {books.length > 0 && <div className="catalog-segmented" role="group" aria-label="Filtrar por origen">
          {origins.map(([value, label]) => <button type="button" key={value} className={activeOrigin === value ? 'active' : ''} aria-pressed={activeOrigin === value}
            disabled={value !== 'all' && !counts[value]} onClick={() => setOrigin(value)}>{label}</button>)}
        </div>}
        <div className="catalog-view">
          <span>Vista:</span>
          <div className="catalog-segmented" role="group" aria-label="Tipo de vista">
            <button type="button" className={view === 'list' ? 'active' : ''} aria-pressed={view === 'list'} aria-label="Ver como lista" onClick={() => changeView('list')}><List aria-hidden="true" /></button>
            <button type="button" className={view === 'grid' ? 'active' : ''} aria-pressed={view === 'grid'} aria-label="Ver como cuadrícula" onClick={() => changeView('grid')}><LayoutGrid aria-hidden="true" /></button>
          </div>
        </div>
      </div>

      {(error || warning) && <div className="catalog-state catalog-alert" role="alert"><p>{error || warning}</p><button type="button" className="button primary" disabled={loading} onClick={() => setRetry(value => value + 1)}>Reintentar búsqueda</button></div>}
      {!searching && <div className="catalog-state catalog-empty">
        <span className="catalog-empty-icon"><BookOpen aria-hidden="true" /></span>
        <h2>Escribe para buscar</h2>
        <p>Encuentra la obra por título, autor o ISBN y selecciona el resultado correcto.</p>
        <button type="button" className="catalog-pill-button" onClick={() => search(suggestions[0][1], suggestions[0][2])}>Probar con “{suggestions[0][0]}”<ChevronRight aria-hidden="true" /></button>
      </div>}
      {!error && !warning && !loading && searching && books.length === 0 && <div className="catalog-state catalog-empty">
        <span className="catalog-empty-icon"><Search aria-hidden="true" /></span>
        <h2>No encontramos libros</h2>
        <p>Prueba con otro criterio o revisa la escritura.</p>
      </div>}

      {loading && !books.length && <div className={`catalog-skeletons is-${view}`} aria-hidden="true">{[0, 1, 2].map(item => <span key={item} className="catalog-skeleton"><span /><span><span /><span /><span /></span></span>)}</div>}
      <div className={`catalog-result-list is-${view}`} aria-busy={loading}>
        {visible.map(book => <ResultCard book={book} key={book.id} />)}
      </div>
      {hasMore && !error && !warning && <div className="catalog-state catalog-load-more"><button type="button" className="catalog-pill-button" disabled={loading} onClick={() => { setStartIndex(nextStartIndex); setCursor(nextCursor); setRetry(value => value + 1) }}>{loading ? 'Cargando…' : 'Ver más resultados'}<ChevronRight aria-hidden="true" /></button></div>}
    </section>
  )
}
