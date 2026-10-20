import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { BookOpen, MoreHorizontal } from 'lucide-react'
import './LibraryPage.css'
import BookCover from '../components/BookCover'
import { useLibrary } from '../context/LibraryContext'

export default function LibraryPage() {
  const { books, loading, loadError, updateStatus, removeBook } = useLibrary()
  const [filter, setFilter] = useState('Todos')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  const shown = filter === 'Todos' ? books : books.filter(book => book.status === filter)
  const changeStatus = async (book, status) => {
    setError('')
    if (status === 'Terminado' || (status === 'Leyendo' && !book.pageCount)) {
      navigate(`/library/${encodeURIComponent(book.id)}`)
      return
    }
    setBusy(true)
    try { await updateStatus(book.id, status) }
    catch (cause) { setError(cause.message || 'No se pudo registrar el cambio de lectura.') }
    finally { setBusy(false) }
  }
  return <section className="page-width page reader-library" aria-labelledby="reader-library-heading">
    <span className="kicker">TU RECORRIDO LECTOR</span><h2 className="page-title" id="reader-library-heading">Mi biblioteca</h2><p className="reader-library-lead">Todos los mundos que habitan en ti.</p>
    <div className="tabs reader-library-filters" role="group" aria-label="Filtrar biblioteca por estado">{['Todos', 'Leyendo', 'Pendiente', 'Terminado', 'Abandonado'].map(item => <button className={filter === item ? 'active' : ''} aria-pressed={filter === item} onClick={() => setFilter(item)} key={item}>{item}</button>)}</div>
    {error && <p className="notice" role="alert">{error}</p>}
    {loading && <p role="status">Cargando biblioteca…</p>}
    {loadError && <p role="alert">{loadError}</p>}
    {!loading && !loadError && shown.length === 0 && <div className="reader-library-empty"><BookOpen size={36} strokeWidth={1.25} aria-hidden="true" /><h3>{books.length ? 'No hay libros en este estado' : 'Tu biblioteca empieza con una historia'}</h3><p>{books.length ? 'Prueba otro filtro para encontrar tus lecturas.' : 'Explora el catálogo y reúne aquí los libros que te acompañan.'}</p>{!books.length && <Link className="button primary" to="/books">Explorar libros</Link>}</div>}
    <div className="reader-library-grid">{shown.map(book => {
      const progress = typeof book.progress === 'number' && Number.isFinite(book.progress) ? Math.max(0, Math.min(100, book.progress)) : null
      const state = { Leyendo: 'reading', Pendiente: 'pending', Terminado: 'finished', Abandonado: 'abandoned' }[book.status] || 'pending'
      return <article className={`reader-book-card reader-book--${state}`} key={book.id}>
        <Link className="reader-book-cover" to={`/library/${encodeURIComponent(book.id)}`} aria-label={`Abrir ${book.title}`}><BookCover book={book} /></Link>
        <div className="reader-book-info"><h3><Link to={`/library/${encodeURIComponent(book.id)}`}>{book.title}</Link></h3><p>{book.author || 'Autor no disponible'}</p></div>
        {book.status === 'Leyendo' && progress !== null && <div className="reader-book-progress"><progress value={progress} max="100" aria-label={`Progreso de ${book.title}`} /><span>{Math.round(progress)}%</span></div>}
        <span className="reader-book-status">{book.status}</span>
        <details className="reader-book-actions"><summary aria-label={`Gestionar ${book.title}`}><MoreHorizontal size={19} aria-hidden="true" /><span>Gestionar</span></summary><div>
          <Link to={`/library/${encodeURIComponent(book.id)}`}>Ver ficha y registrar avance</Link>
          <label>Estado<select disabled={busy} value={book.status} aria-label={`Estado de ${book.title}`} onChange={event => changeStatus(book, event.target.value)}>
            <option>Leyendo</option><option disabled={book.status !== 'Pendiente'}>Pendiente</option><option disabled={!['Pendiente', 'Leyendo', 'Terminado'].includes(book.status)}>Terminado</option><option disabled>Abandonado</option>
          </select></label>
          <button className="reader-book-remove" disabled={busy} onClick={async () => { setBusy(true); setError(''); try { await removeBook(book) } catch { setError('No se pudo retirar el libro de tu biblioteca.') } finally { setBusy(false) } }}>Retirar de mi biblioteca</button>
        </div></details>
      </article>
    })}</div>
    <p className="notice">Puedes abandonar un libro en “Registrar avance”; el motivo es opcional. Al retirar un libro se recalcula tu perfil sin esa experiencia.</p>
  </section>
}
