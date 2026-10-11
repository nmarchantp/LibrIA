import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import BookCover from '../components/BookCover'
import { searchBookCatalog } from '../services/booksService'

export default function BooksPage() {
  const [query, setQuery] = useState('')
  const [googleBooks, setGoogleBooks] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    let active = true

    const loadBooks = async () => {
      try {
        setLoading(true)
        setError('')
        setWarning('')
        const results = await searchBookCatalog(query)
        if (active) { setGoogleBooks(results.books); setWarning(results.warning) }
      } catch {
        if (active) { setGoogleBooks([]); setError('No se pudo consultar el catálogo. Inténtalo nuevamente.') }
      } finally {
        if (active) setLoading(false)
      }
    }

    const timer = setTimeout(loadBooks, 350)
    return () => { active = false; clearTimeout(timer) }
  }, [query, retry])

  const visible = googleBooks

  return (
    <section className="page-width page">
      <span className="kicker">ENCUENTRA TU PRÓXIMA LECTURA</span>
      <h1 className="page-title">Explora nuevos mundos</h1>
      <p className="page-lead">Una historia para cada momento. Encuentra tu próxima lectura por título o autor.</p>
      <label className="search-box">
        <Search />
        <input type="search" aria-label="Buscar libros o autores" value={query} onChange={e => setQuery(e.target.value)} placeholder="Buscar libros o autores…" />
      </label>
      <div className="result-line" role="status" aria-live="polite">
        <strong>{loading ? 'Buscando…' : `${visible.length} libros`}</strong>
      </div>
      {(error || warning) && <div className="catalog-state" role="alert"><p>{error || warning}</p><button type="button" className="button primary" disabled={loading} onClick={() => setRetry(value => value + 1)}>Reintentar búsqueda</button></div>}
      {!error && !warning && !loading && visible.length === 0 && <div className="catalog-state"><Search size={28} /><h2>No encontramos libros</h2><p>Prueba con otro título, el nombre del autor o una búsqueda más corta.</p></div>}
      <div className="book-grid" aria-busy={loading}>
        {visible.map(book => (
          <Link className="book-tile" to={`/books/${book.id}`} key={book.id}>
            <BookCover book={book} />
            {book.status && <span className="pill">{book.status}</span>}
            <h3>{book.title}</h3>
            <p>{book.author} · {book.year}</p>
          </Link>
        ))}
      </div>
    </section>
  )
}
