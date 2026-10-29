import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { BookOpen, Check, Clock3, MoreHorizontal, SlidersHorizontal, X } from 'lucide-react'
import './LibraryPage.css'
import BookCover from '../components/BookCover'
import ProfileReadingStats from '../components/ProfileReadingStats'
import LibraryManageModal from '../components/LibraryManageModal'
import LibraryRemoveModal from '../components/LibraryRemoveModal'
import { useLibrary } from '../context/LibraryContext'

export default function LibraryPage() {
  const { books, loading, loadError, updateStatus, removeBook } = useLibrary()
  const [filter, setFilter] = useState('Todos')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [selectedId, setSelectedId] = useState(null)
  const [removeId, setRemoveId] = useState(null)
  const [removeError, setRemoveError] = useState('')
  const [notice, setNotice] = useState('')
  const [isManagingLibrary, setIsManagingLibrary] = useState(false)
  const removalInProgress = useRef(false)
  const selectedBook = books.find(book => book.id === selectedId)
  const bookToRemove = books.find(book => book.id === removeId)
  const closeManagement = () => { setSelectedId(null); setError('') }
  const navigate = useNavigate()
  const shown = filter === 'Todos' ? books : books.filter(book => book.status === filter)
  useEffect(() => {
    if (!notice) return undefined
    const timeout = window.setTimeout(() => setNotice(''), 4000)
    return () => window.clearTimeout(timeout)
  }, [notice])
  const changeStatus = async (book, status) => {
    setError('')
    if (status === 'Terminado' || (status === 'Leyendo' && !book.pageCount && !book.editionOptional)) {
      closeManagement()
      navigate(`/library/${encodeURIComponent(book.id)}`)
      return
    }
    setBusy(true)
    try { await updateStatus(book.id, status) }
    catch (cause) { setError(cause.message || 'No se pudo registrar el cambio de lectura.') }
    finally { setBusy(false) }
  }
  const confirmRemoval = async book => {
    if (removalInProgress.current || busy) return
    removalInProgress.current = true
    setBusy(true); setRemoveError(''); setNotice('')
    try {
      await removeBook(book)
      setRemoveId(null)
      setNotice('Libro retirado de tu biblioteca')
    } catch (cause) {
      setRemoveError(cause.message || 'No se pudo retirar el libro de tu biblioteca. Inténtalo nuevamente.')
    } finally { removalInProgress.current = false; setBusy(false) }
  }
  return <section className="page-width page reader-library" aria-labelledby="reader-library-heading">
    <span className="kicker">TU RECORRIDO LECTOR</span><h2 className="page-title" id="reader-library-heading">Mi biblioteca</h2><p className="reader-library-lead">Todos los mundos que habitan en ti.</p>
    <div className="reader-profile-summary"><ProfileReadingStats books={books} loading={loading} loadError={loadError} /></div>
    <div className="reader-library-toolbar">
    <div className="tabs reader-library-filters" role="group" aria-label="Filtrar biblioteca por estado">{['Todos', 'Leyendo', 'Pendiente', 'Terminado', 'Abandonado'].map(item => <button className={filter === item ? 'active' : ''} aria-pressed={filter === item} onClick={() => setFilter(item)} key={item}>{item}</button>)}</div>
      <button type="button" className="reader-library-manage-toggle" aria-pressed={isManagingLibrary} onClick={() => setIsManagingLibrary(current => !current)}>
        {isManagingLibrary ? <Check size={16} aria-hidden="true" /> : <SlidersHorizontal size={16} aria-hidden="true" />}
        {isManagingLibrary ? 'Finalizar gestión' : 'Gestionar mi biblioteca'}
      </button>
    </div>
    {error && !selectedBook && <p className="notice" role="alert">{error}</p>}
    {loading && <p role="status">Cargando biblioteca…</p>}
    {loadError && <p role="alert">{loadError}</p>}
    {!loading && !loadError && shown.length === 0 && <div className="reader-library-empty"><BookOpen size={36} strokeWidth={1.25} aria-hidden="true" /><h3>{books.length ? 'No hay libros en este estado' : 'Tu biblioteca empieza con una historia'}</h3><p>{books.length ? 'Prueba otro filtro para encontrar tus lecturas.' : 'Explora el catálogo y reúne aquí los libros que te acompañan.'}</p>{!books.length && <Link className="button primary" to="/books">Explorar libros</Link>}</div>}
    <div className="reader-library-grid">{shown.map(book => {
      const StatusIcon = { Leyendo: BookOpen, Pendiente: Clock3, Terminado: Check, Abandonado: X }[book.status] || Clock3
      const state = { Leyendo: 'reading', Pendiente: 'pending', Terminado: 'finished', Abandonado: 'abandoned' }[book.status] || 'pending'
      return <article className={`reader-book-card reader-book--${state}`} key={book.id}>
        <Link className="reader-book-cover" to={`/library/${encodeURIComponent(book.id)}`} aria-label={`Abrir ${book.title}, ${book.status}`}><BookCover book={book} /><span className="reader-book-status"><StatusIcon size={12} aria-hidden="true" /><span>{book.status}</span></span></Link>
        <div className="reader-book-info"><h3><Link to={`/library/${encodeURIComponent(book.id)}`} title={book.title}>{book.title}</Link></h3><p title={book.author}>{book.author || 'Autor no disponible'}</p></div>
        {isManagingLibrary && <>
          <button type="button" className="reader-book-remove-icon" title="Retirar de mi biblioteca" aria-label={`Retirar ${book.title} de mi biblioteca`}
            onClick={event => { event.preventDefault(); event.stopPropagation(); setRemoveError(''); setRemoveId(book.id) }}><X size={15} aria-hidden="true" /></button>
          <button type="button" className="reader-book-manage" aria-label={`Gestionar ${book.title}`} onClick={() => { setError(''); setSelectedId(book.id) }}><MoreHorizontal size={19} aria-hidden="true" />Gestionar</button>
        </>}
      </article>
    })}</div>
    {selectedBook && <LibraryManageModal book={selectedBook} busy={busy} error={error} onClose={closeManagement} onChangeStatus={changeStatus} />}
    {bookToRemove && <LibraryRemoveModal book={bookToRemove} busy={busy} error={removeError} onClose={() => { if (!busy) { setRemoveId(null); setRemoveError('') } }} onConfirm={() => confirmRemoval(bookToRemove)} />}
    {notice && <p className="reader-library-toast" role="status" aria-live="polite">{notice}</p>}
    <p className="notice">Puedes abandonar un libro en “Registrar avance”; el motivo es opcional.</p>
  </section>
}
