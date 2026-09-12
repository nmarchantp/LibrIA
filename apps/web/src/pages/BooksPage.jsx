import { Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import BookCover from '../components/BookCover'
import { useLibrary } from '../context/LibraryContext'
import { searchGoogleBooks } from '../services/booksService'

export default function BooksPage() {
  const { books } = useLibrary()
  const [query, setQuery] = useState('')
  const [googleBooks, setGoogleBooks] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let active = true

    if (!query.trim()) {
      setGoogleBooks([])
      return () => { active = false }
    }

    const loadBooks = async () => {
      try {
        setLoading(true)
        const results = await searchGoogleBooks(query)
        if (active) setGoogleBooks(results)
      } catch (error) {
        if (active) setGoogleBooks([])
      } finally {
        if (active) setLoading(false)
      }
    }

    loadBooks()
    return () => { active = false }
  }, [query])

  const sourceBooks = googleBooks.length > 0 ? googleBooks : books
  const visible = useMemo(
    () => sourceBooks.filter(book => `${book.title} ${book.author}`.toLowerCase().includes(query.toLowerCase())),
    [sourceBooks, query]
  )

  return (
    <section className="page-width page">
      <span className="kicker">ENCUENTRA TU PRÓXIMA LECTURA</span>
      <h1 className="page-title">Explora nuevos mundos</h1>
      <label className="search-box">
        <Search />
        <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Buscar libros o autores…" />
      </label>
      <div className="result-line">
        <strong>{loading ? 'Buscando…' : `${visible.length} libros`}</strong>
      </div>
      <div className="book-grid">
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
