import { Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import BookCover from '../components/BookCover'
import { useLibrary } from '../context/LibraryContext'

export default function RecommendationsPage() {
  const { books } = useLibrary()
  const scores = [94, 89, 87, 81]
  return <section className="page-width page community-page">
    <span className="kicker">PARA TI</span><h1 className="page-title">LibrIA te recomienda</h1>
    <p className="page-lead">Una primera selección basada en tu biblioteca de demostración.</p>
    <div className="recommendation-grid">
      {books.slice(0, 4).map((book, index) => <Link className="recommendation-card" to={`/books/${book.id}`} key={book.id}>
        <BookCover book={book} /><span className="match-score">{scores[index] ?? 78}% match</span><h2>{book.title}</h2><p>{book.author}</p>
      </Link>)}
    </div>
    <p className="demo-notice"><Sparkles size={17} /> Recomendaciones demostrativas; todavía no son generadas por IA.</p>
  </section>
}
