import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { BookOpen, Check, Clock3, MoreHorizontal, X } from 'lucide-react'
import './LibraryPage.css'
import BookCover from '../components/BookCover'
import ProfileReadingStats from '../components/ProfileReadingStats'
import LibraryManageModal from '../components/LibraryManageModal'
import { useLibrary } from '../context/LibraryContext'

export default function LibraryPage() {
  const { books, loading, loadError, updateStatus, removeBook } = useLibrary()
  const [filter, setFilter] = useState('Todos')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [selectedId, setSelectedId] = useState(null)
  const selectedBook = books.find(book => book.id === selectedId)
  const closeManagement = () => { setSelectedId(null); setError('') }
  const navigate = useNavigate()
  const shown = filter === 'Todos' ? books : books.filter(book => book.status === filter)
  const changeStatus = async (book, status) => {
    setError('')
    if (status === 'Terminado' || (status === 'Leyendo' && !book.pageCount)) {
      closeManagement()
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
    <div className="reader-profile-summary"><ProfileReadingStats books={books} loading={loading} loadError={loadError} /></div>
    <div className="tabs reader-library-filters" role="group" aria-label="Filtrar biblioteca por estado">{['Todos', 'Leyendo', 'Pendiente', 'Terminado', 'Abandonado'].map(item => <button className={filter === item ? 'active' : ''} aria-pressed={filter === item} onClick={() => setFilter(item)} key={item}>{item}</button>)}</div>
    {error && !selectedBook && <p className="notice" role="alert">{error}</p>}
    {loading && <p role="status">Cargando biblioteca…</p>}
    {loadError && <p role="alert">{loadError}</p>}
    {!loading && !loadError && shown.length === 0 && <div className="reader-library-empty"><BookOpen size={36} strokeWidth={1.25} aria-hidden="true" /><h3>{books.length ? 'No hay libros en este estado' : 'Tu biblioteca empieza con una historia'}</h3><p>{books.length ? 'Prueba otro filtro para encontrar tus lecturas.' : 'Explora el catálogo y reúne aquí los libros que te acompañan.'}</p>{!books.length && <Link className="button primary" to="/books">Explorar libros</Link>}</div>}
    <div className="reader-library-grid">{shown.map(book => {
      const StatusIcon = { Leyendo: BookOpen, Pendiente: Clock3, Terminado: Check, Abandonado: X }[book.status] || Clock3
      const state = { Leyendo: 'reading', Pendiente: 'pending', Terminado: 'finished', Abandonado: 'abandoned' }[book.status] || 'pending'
      return <article className={`reader-book-card reader-book--${state}`} key={book.id}>
        <Link className="reader-book-cover" to={`/library/${encodeURIComponent(book.id)}`} aria-label={`Abrir ${book.title}, ${book.status}`}><BookCover book={book} /><span className="reader-book-status"><StatusIcon size={12} aria-hidden="true" />{book.status}</span></Link>
        <div className="reader-book-info"><h3><Link to={`/library/${encodeURIComponent(book.id)}`} title={book.title}>{book.title}</Link></h3><p title={book.author}>{book.author || 'Autor no disponible'}</p></div>
        <button type="button" className="reader-book-manage" aria-label={`Gestionar ${book.title}`} onClick={() => { setError(''); setSelectedId(book.id) }}><MoreHorizontal size={19} aria-hidden="true" />Gestionar</button>
      </article>
    })}</div>
    {selectedBook && <LibraryManageModal book={selectedBook} busy={busy} error={error} onClose={closeManagement} onChangeStatus={changeStatus} onRemove={async book => {
      setBusy(true); setError('')
      try { await removeBook(book); closeManagement() }
      catch { setError('No se pudo retirar el libro de tu biblioteca.') }
      finally { setBusy(false) }
    }} />}
    <p className="notice">Puedes abandonar un libro en “Registrar avance”; el motivo es opcional. Al retirar un libro se recalcula tu perfil sin esa experiencia.</p>
  </section>
}
