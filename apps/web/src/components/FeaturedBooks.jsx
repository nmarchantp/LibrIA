import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, ChevronRight, Compass } from 'lucide-react'
import RatingStar from './RatingStar'
import { searchBookCatalog } from '../services/booksService'
import './FeaturedBooks.css'

// Curated works, looked up by ISBN so every catalog resolves them; genre, original year, tone and title overrides are editorial.
const featured = [
  { isbn: '9788418637032', title: 'Coraline (edición ilustrada)', genre: 'Fantasía oscura', year: 2002, tone: '#7b5cc4' },
  { isbn: '9786073902427', genre: 'Romantasy', year: 2023, tone: '#c4506b' },
  { isbn: '9781781101315', genre: 'Magia clásica', year: 1997, tone: '#c9853f' },
  { isbn: '9788401342585', genre: 'Realismo mágico', year: 1982, tone: '#3f9a89' },
]
const cacheKey = 'libria_featured_books_v2'
const cacheTime = 30 * 60 * 1000

function readCache() {
  try {
    const cached = JSON.parse(sessionStorage.getItem(cacheKey))
    return cached && Date.now() - cached.at < cacheTime && Array.isArray(cached.books) ? cached.books : null
  } catch { return null }
}

export default function FeaturedBooks({ fallback }) {
  const [books, setBooks] = useState(readCache)
  useEffect(() => {
    if (books) return
    const controller = new AbortController()
    Promise.allSettled(featured.map(item => searchBookCatalog(item.isbn, 'isbn', { signal: controller.signal }))).then(results => {
      if (controller.signal.aborted) return
      const found = results.flatMap((result, index) => {
        const book = result.status === 'fulfilled' && result.value.books[0]
        return book ? [{ ...featured[index], id: book.id, title: featured[index].title || book.title, author: book.author, image: book.image, pageCount: book.pageCount, averageRating: book.averageRating, libria: book.catalogOrigin === 'libria' }] : []
      })
      setBooks(found)
      try { if (found.length) sessionStorage.setItem(cacheKey, JSON.stringify({ at: Date.now(), books: found })) } catch { /* Only a convenience. */ }
    })
    return () => controller.abort()
  }, [books])

  if (books && !books.length) return fallback
  return <section className="featured-books" aria-labelledby="featured-books-heading" aria-busy={!books}>
    <div className="featured-books-heading">
      <div><h2 id="featured-books-heading"><Compass aria-hidden="true" />Inspiración para tu estantería</h2>
        <p>Elige una obra destacada en un clic o escribe arriba para explorar todo el catálogo.</p></div>
      <span>Selección destacada · {featured.length} obras</span>
    </div>
    <ul className="featured-books-grid">
      {books ? books.map(book => <li key={book.isbn}>
        <Link className="featured-book" to={`/books/${book.id}`} style={{ '--tone': book.tone }}>
          <span className="featured-book-cover">
            {book.image ? <img src={book.image} alt="" loading="lazy" /> : <span className="featured-book-fallback"><BookOpen aria-hidden="true" /><strong>{book.title}</strong></span>}
            <span className="featured-book-genre">{book.genre}</span>
            {book.averageRating && <span className="featured-book-rating" aria-label={`Valoración promedio ${Number(book.averageRating).toFixed(1)}`}><RatingStar selected />{Number(book.averageRating).toFixed(1)}</span>}
            {book.pageCount > 0 && <span className="featured-book-pages">{book.pageCount} pág.</span>}
            <span className="featured-book-year">{book.year}</span>
          </span>
          <span className="featured-book-copy"><strong>{book.title}</strong><small>{book.author}</small></span>
          <span className="featured-book-footer"><span>{book.libria ? 'LibrIAverse' : 'Google Books'}</span><span className="featured-book-cta">Ver ficha<ChevronRight aria-hidden="true" /></span></span>
        </Link>
      </li>) : featured.map(item => <li key={item.isbn} className="featured-book-skeleton" aria-hidden="true"><span /><span /><span /></li>)}
    </ul>
  </section>
}
