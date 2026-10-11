import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import BookCover from '../components/BookCover'
import { useLibrary } from '../context/LibraryContext'

export default function LibraryPage() {
  const { books, loading, loadError, updateStatus } = useLibrary()
  const [filter, setFilter] = useState('Todos')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  const shown = filter === 'Todos' ? books : books.filter(book => book.status === filter)
  const changeStatus = async (book, status) => {
    setError('')
    if (status === 'Terminado' || (status === 'Leyendo' && !book.pageCount)) {
      navigate(`/reading/${encodeURIComponent(book.id)}`)
      return
    }
    setBusy(true)
    try { await updateStatus(book.id, status) }
    catch (cause) { setError(cause.message || 'No se pudo registrar el cambio de lectura.') }
    finally { setBusy(false) }
  }
  return <section className="page-width page">
    <span className="kicker">TU RECORRIDO LECTOR</span><h1 className="page-title">Mi biblioteca</h1>
    <div className="tabs">{['Todos', 'Leyendo', 'Pendiente', 'Terminado', 'Abandonado'].map(item => <button className={filter === item ? 'active' : ''} onClick={() => setFilter(item)} key={item}>{item}</button>)}</div>
    {error && <p className="notice" role="alert">{error}</p>}
    {loading && <p role="status">Cargando biblioteca…</p>}
    {loadError && <p role="alert">{loadError}</p>}
    <div className="library-list">{shown.map(book => <article className="library-row" key={book.id}>
      <Link to={`/books/${book.id}`}><BookCover book={book} /></Link>
      <div className="library-details"><h2>{book.title}</h2><p>{book.author}</p><Link to={`/reading/${encodeURIComponent(book.id)}`}>Reseñar, registrar avance o terminar</Link></div>
      <select disabled={busy} value={book.status} aria-label={`Estado de ${book.title}`} onChange={event => changeStatus(book, event.target.value)}>
        <option>Leyendo</option><option disabled={book.status !== 'Pendiente'}>Pendiente</option><option disabled={!['Pendiente', 'Leyendo', 'Terminado'].includes(book.status)}>Terminado</option><option disabled>Abandonado</option>
      </select>
    </article>)}</div>
    <p className="notice">Para abandonar un libro, indica el motivo en “Registrar avance”.</p>
  </section>
}
