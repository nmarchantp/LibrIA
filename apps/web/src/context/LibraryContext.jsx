import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { books as initialBooks } from '../data'
import { apiRequest } from '../api/client'
import { useAuth } from './AuthContext'

const LibraryContext = createContext(null)
const catalogBooks = initialBooks.map(book => ({ ...book, status: 'Pendiente', progress: 0 }))
const statusLabels = { pending: 'Pendiente', reading: 'Leyendo', finished: 'Terminado', abandoned: 'Abandonado' }
const withReading = (book, reading) => reading ? {
  ...book, status: statusLabels[reading.status] || book.status,
  progress: reading.progress_percent, pageCount: reading.total_pages, readingId: reading.reading_id,
} : book

export function LibraryProvider({ children }) {
  const { user } = useAuth()
  const [books, setBooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const readings = useRef({})
  useEffect(() => {
    let active = true
    readings.current = {}
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
            id: item.book_ref, title: item.book_title, author: '', color: '#173f35',
            accent: '#ffb65c', initial: item.book_title.charAt(0).toUpperCase(),
          }, item))
          return [...current.map(book => withReading(book, readings.current[String(book.id)])), ...restored]
        })
      }).catch(() => { if (active) setLoadError('No se pudo cargar tu biblioteca. Recarga para reintentar.') })
        .finally(() => { if (active) setLoading(false) })
    }
    return () => { active = false }
  }, [user?.id])
  const recordEvent = async (book, event, extra = {}) => {
    const token = localStorage.getItem('libria_token')
    if (!token) throw new Error('Inicia sesión para registrar una lectura.')
    const pageCount = Number(extra.page_count || book.pageCount)
    if (!Number.isInteger(pageCount) || pageCount < 1) throw new Error('Indica el total de páginas del libro.')
    const result = await apiRequest('/readings/events', {
      method: 'POST', headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ book_ref: String(book.id), book_title: book.title, page_count: pageCount, event, ...extra, reading_id: event === 'start' ? null : book.readingId }),
    })
    if (token !== localStorage.getItem('libria_token')) throw new Error('La sesión cambió. Recarga tu biblioteca.')
    const status = { start: 'Leyendo', progress: 'Leyendo', correction: 'Leyendo', finish: 'Terminado', abandon: 'Abandonado' }[event]
    readings.current[String(book.id)] = {
      reading_id: result.reading_id, book_ref: String(book.id), book_title: book.title, status: result.status,
      progress_percent: result.progress_percent, total_pages: pageCount,
    }
    setBooks(current => {
      const updated = { ...book, status, progress: result.progress_percent, pageCount, readingId: result.reading_id }
      return current.some(item => String(item.id) === String(book.id))
        ? current.map(item => String(item.id) === String(book.id) ? updated : item) : [...current, updated]
    })
    return result
  }
  const updateStatus = async (id, status) => {
    const book = books.find(item => String(item.id) === String(id))
    if (!book) throw new Error('Agrega primero el libro a tu biblioteca.')
    if (book.status === status) return
    if ((status === 'Leyendo' || status === 'Terminado') && !book.pageCount) {
      throw new Error('Indica primero el total de páginas en Registrar avance.')
    }
    if (status === 'Leyendo') return recordEvent(book, 'start')
    if (status === 'Terminado') return recordEvent(book, 'finish')
    throw new Error('Registra el cambio desde la experiencia de lectura.')
  }
  const addBook = useCallback(async (book) => {
    if (!book) return
    const token = localStorage.getItem('libria_token')
    if (!token) throw new Error('Inicia sesion para agregar libros.')
    const reading = await apiRequest('/readings/library', {
      method: 'POST', headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ book_ref: String(book.id), book_title: book.title, page_count: book.pageCount || null }),
    })
    if (token !== localStorage.getItem('libria_token')) throw new Error('La sesión cambió. Recarga tu biblioteca.')
    readings.current[String(book.id)] = reading
    setBooks(current => current.some(item => String(item.id) === String(book.id))
      ? current.map(item => String(item.id) === String(book.id) ? withReading({ ...item, ...book }, reading) : item)
      : [...current, withReading(book, reading)])
  }, [])
  const getBook = useCallback((id) => books.find(book => String(book.id) === String(id))
    ?? catalogBooks.find(book => String(book.id) === String(id)), [books])
  return <LibraryContext.Provider value={{ books, loading, loadError, updateStatus, recordEvent, addBook, getBook }}>{children}</LibraryContext.Provider>
}

// Este archivo exporta deliberadamente el proveedor y su hook de acceso.
// eslint-disable-next-line react-refresh/only-export-components
export function useLibrary() {
  const context = useContext(LibraryContext)
  if (!context) throw new Error('useLibrary debe utilizarse dentro de LibraryProvider')
  return context
}
