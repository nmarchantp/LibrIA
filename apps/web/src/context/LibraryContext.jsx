import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { books as initialBooks } from '../data'
import { apiRequest } from '../api/client'
import { useAuth } from './AuthContext'
import { normalizeGoogleBook } from '../services/booksService'
import { librarySelection } from '../services/librarySelection'
import { withReading, eventPageCount } from '../services/readingState'

const LibraryContext = createContext(null)
const catalogBooks = initialBooks.map(book => ({ ...book, status: 'Pendiente', progress: 0 }))

export function LibraryProvider({ children }) {
  const { user } = useAuth()
  const [books, setBooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const readings = useRef({})
  const additionKeys = useRef(new Map())
  const [identityRefresh,setIdentityRefresh] = useState(0)
  useEffect(()=>{
    const refresh=()=>setIdentityRefresh(value=>value+1)
    window.addEventListener('libria:catalog-identity-changed',refresh)
    return ()=>window.removeEventListener('libria:catalog-identity-changed',refresh)
  },[])
  useEffect(() => {
    let active = true
    readings.current = {}
    additionKeys.current.clear()
    setBooks([])
    setLoading(Boolean(user?.id))
    setLoadError('')
    if (user?.id) {
      const token = localStorage.getItem('libria_token')
      apiRequest('/readings/me', { headers: { Authorization: `Bearer ${token}` } }).then(data => {
        if (!active) return
        readings.current = { ...Object.fromEntries(data.map(item => [item.book_ref, item])), ...readings.current }
        setBooks(current => {
          const existing = new Set(current.map(book => String(book.id)))
          const restored = data.filter(item => !existing.has(item.book_ref)).map(item => withReading({
            id: item.book_ref, title: item.book_title, originalTitle: item.book_title, author: '', color: '#173f35',
            accent: '#ffb65c', initial: item.book_title.charAt(0).toUpperCase(),
            ...(item.catalog_volume ? normalizeGoogleBook(item.catalog_volume) : {}),
          }, item))
          return [...current.map(book => withReading(book, readings.current[String(book.id)])), ...restored]
        })
      }).catch(() => { if (active) setLoadError('No se pudo cargar tu biblioteca. Recarga para reintentar.') })
        .finally(() => { if (active) setLoading(false) })
    }
    return () => { active = false }
  }, [user?.id,identityRefresh])
  const recordEvent = async (book, event, extra = {}) => {
    const token = localStorage.getItem('libria_token')
    if (!token) throw new Error('Inicia sesión para registrar una lectura.')
    const pageCount = eventPageCount(book, extra)
    if (book.status === 'Pendiente' && ['progress', 'finish'].includes(event)) {
      const started = await recordEvent(book, 'start', { page_count: pageCount })
      return recordEvent({ ...book, status: 'Leyendo', readingId: started.reading_id, pageCount, currentPage: 0 }, event, extra)
    }
    const result = await apiRequest('/readings/events', {
      method: 'POST', headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ book_ref: String(book.id), book_title: book.originalTitle || book.title, edition_id: book.editionId || null, page_count: pageCount, event, ...extra, reading_id: event === 'start' ? null : book.readingId }),
    })
    if (token !== localStorage.getItem('libria_token')) throw new Error('La sesión cambió. Recarga tu biblioteca.')
    const status = { start: 'Leyendo', progress: 'Leyendo', correction: 'Leyendo', finish: 'Terminado', abandon: 'Abandonado' }[event]
    readings.current[String(book.id)] = {
      reading_id: result.reading_id, book_ref: String(book.id), book_title: book.originalTitle || book.title, status: result.status,
      work_id: result.work_id, edition_id: result.edition_id,
      edition_optional: Boolean(book.editionOptional),
      progress_percent: result.progress_percent, current_page: result.current_page, total_pages: result.total_pages,
      reflection: result.reflection,
      started_at: result.started_at, finished_at: result.finished_at, notebook: book.notebook || {},
    }
    setBooks(current => {
      const updated = { ...book, status, reflection: result.reflection, progress: result.progress_percent, currentPage: result.current_page, pageCount: result.total_pages, readingId: result.reading_id, workId: result.work_id, editionId: result.edition_id,
        startedAt: event === 'start' && !book.startedAt ? new Date().toISOString() : book.startedAt,
        finishedAt: event === 'finish' ? new Date().toISOString() : book.finishedAt }
      return current.some(item => String(item.id) === String(book.id))
        ? current.map(item => String(item.id) === String(book.id) ? updated : item) : [...current, updated]
    })
    return result
  }
  const updateStatus = async (id, status) => {
    const book = books.find(item => String(item.id) === String(id))
    if (!book) throw new Error('Agrega primero el libro a tu biblioteca.')
    if (book.status === status) return
    if ((status === 'Leyendo' || status === 'Terminado') && !book.pageCount && !book.editionOptional) {
      throw new Error('Indica primero el total de páginas en Registrar avance.')
    }
    if (status === 'Leyendo') return recordEvent(book, 'start')
    if (status === 'Terminado') return recordEvent(book, 'finish')
    throw new Error('Registra el cambio desde la experiencia de lectura.')
  }
  const updateTotalPages = async (id, totalPages) => {
    const book = books.find(item => String(item.id) === String(id))
    if (!book?.readingId) throw new Error('No se encontró esta lectura en tu biblioteca.')
    const token = localStorage.getItem('libria_token')
    const result = await apiRequest(`/readings/${book.readingId}/total-pages`, {
      method: 'PATCH', headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ total_pages: Number(totalPages) }),
    })
    if (readings.current[String(book.id)]) {
      readings.current[String(book.id)] = { ...readings.current[String(book.id)],
        total_pages: result.total_pages, current_page: result.current_page, progress_percent: result.progress_percent }
    }
    setBooks(current => current.map(item => String(item.id) === String(id) ? {
      ...item, pageCount: result.total_pages, currentPage: result.current_page, progress: result.progress_percent,
    } : item))
    return result
  }
  const addBook = useCallback(async (book) => {
    if (!book) return
    const token = localStorage.getItem('libria_token')
    if (!token) throw new Error('Inicia sesion para agregar libros.')
    const selection = librarySelection(book)
    const signature = JSON.stringify(selection)
    if (!additionKeys.current.has(signature)) additionKeys.current.set(signature, crypto.randomUUID())
    const reading = await apiRequest('/readings/library', {
      method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Idempotency-Key': additionKeys.current.get(signature) },
      body: signature,
    })
    if (token !== localStorage.getItem('libria_token')) throw new Error('La sesión cambió. Recarga tu biblioteca.')
    const restored = reading.catalog_volume ? { ...book, ...normalizeGoogleBook(reading.catalog_volume) } : book
    readings.current[String(restored.id)] = reading
    setBooks(current => current.some(item => item.workId === reading.work_id || String(item.id) === String(restored.id))
      ? current.map(item => item.workId === reading.work_id || String(item.id) === String(restored.id) ? withReading({ ...item, ...restored }, reading) : item)
      : [...current, withReading(restored, reading)])
    return reading
  }, [])
  const getBook = useCallback((id) => books.find(book => [book.id, book.workId, book.canonicalWorkId, book.externalId, book.rawVolume?.id, ...(book.references || [])]
    .some(reference => reference != null && String(reference) === String(id)))
    ?? catalogBooks.find(book => String(book.id) === String(id)), [books])
  const removeBook = async book => {
    await apiRequest(`/readings/library/${book.workId}`, { method: 'DELETE', headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` } })
    delete readings.current[String(book.id)]
    setBooks(current => current.filter(item => item.workId !== book.workId))
  }
  const selectReadingEdition = async (book, editionId) => {
    const token = localStorage.getItem('libria_token')
    const reading = await apiRequest(`/readings/${book.readingId}/edition`, {
      method: 'PATCH', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ edition_id: editionId }),
    })
    if (token !== localStorage.getItem('libria_token')) throw new Error('La sesión cambió. Recarga tu biblioteca.')
    const restored = withReading(normalizeGoogleBook(reading.catalog_volume), reading)
    readings.current[String(restored.id)] = reading
    setBooks(current => current.map(item => item.readingId === reading.reading_id ? restored : item))
    return reading
  }
  return <LibraryContext.Provider value={{ books, loading, loadError, updateStatus, updateTotalPages, recordEvent, addBook, removeBook, getBook, selectReadingEdition }}>{children}</LibraryContext.Provider>
}

// Este archivo exporta deliberadamente el proveedor y su hook de acceso.
// eslint-disable-next-line react-refresh/only-export-components
export function useLibrary() {
  const context = useContext(LibraryContext)
  if (!context) throw new Error('useLibrary debe utilizarse dentro de LibraryProvider')
  return context
}
