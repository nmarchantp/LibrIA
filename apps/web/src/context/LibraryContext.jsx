import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { books as initialBooks } from '../data'
import { apiRequest } from '../api/client'
import { useAuth } from './AuthContext'

const LibraryContext = createContext(null)
const statusLabels = { reading: 'Leyendo', finished: 'Terminado', abandoned: 'Abandonado' }
const withReading = (book, reading) => reading ? {
  ...book, status: statusLabels[reading.status] || book.status,
  progress: reading.progress_percent, pageCount: reading.total_pages,
} : book

export function LibraryProvider({ children }) {
  const { user } = useAuth()
  const [books, setBooks] = useState(initialBooks)
  const readings = useRef({})
  useEffect(() => {
    let active = true
    readings.current = {}
    setBooks(initialBooks)
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
      }).catch(() => {})
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
      body: JSON.stringify({ book_ref: String(book.id), book_title: book.title, page_count: pageCount, event, ...extra }),
    })
    const status = { start: 'Leyendo', progress: 'Leyendo', finish: 'Terminado', abandon: 'Abandonado' }[event]
    readings.current[String(book.id)] = {
      book_ref: String(book.id), book_title: book.title, status: result.status,
      progress_percent: result.progress_percent, total_pages: pageCount,
    }
    setBooks(current => current.map(item => String(item.id) === String(book.id)
      ? { ...item, status, progress: result.progress_percent, pageCount } : item))
    return result
  }
  const updateStatus = async (id, status) => {
    const book = books.find(item => String(item.id) === String(id))
    if (!book || book.status === status) return
    if ((status === 'Leyendo' || status === 'Terminado') && !book.pageCount) {
      throw new Error('Indica primero el total de páginas en Registrar avance.')
    }
    if (status === 'Leyendo') return recordEvent(book, 'start')
    if (status === 'Terminado') return recordEvent(book, 'finish')
    setBooks(current => current.map(item => String(item.id) === String(id) ? { ...item, status } : item))
  }
  const addBook = (book) => setBooks(current => {
    if (!book) return current
    const existing = current.some(item => String(item.id) === String(book.id))
    if (existing) {
        return current.map(item => String(item.id) === String(book.id)
          ? withReading({ ...item, ...book }, readings.current[String(book.id)]) : item)
      }
    return [withReading(book, readings.current[String(book.id)]), ...current]
  })
  const getBook = (id) => books.find(book => String(book.id) === String(id))
  return <LibraryContext.Provider value={{ books, updateStatus, recordEvent, addBook, getBook }}>{children}</LibraryContext.Provider>
}

// Este archivo exporta deliberadamente el proveedor y su hook de acceso.
// eslint-disable-next-line react-refresh/only-export-components
export function useLibrary() {
  const context = useContext(LibraryContext)
  if (!context) throw new Error('useLibrary debe utilizarse dentro de LibraryProvider')
  return context
}
