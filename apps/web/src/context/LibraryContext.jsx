import { createContext, useContext, useState } from 'react'
import { books as initialBooks } from '../data'

const LibraryContext = createContext(null)

// Centraliza temporalmente la biblioteca; luego sus acciones llamarán a FastAPI.
export function LibraryProvider({ children }) {
  const [books, setBooks] = useState(initialBooks)
  const updateStatus = (id, status) => setBooks(current => current.map(book => String(book.id) === String(id) ? { ...book, status } : book))
  const addBook = (book) => setBooks(current => {
    if (!book) return current
    const existing = current.some(item => String(item.id) === String(book.id))
    if (existing) {
      return current.map(item => String(item.id) === String(book.id) ? { ...item, ...book } : item)
    }
    return [book, ...current]
  })
  const getBook = (id) => books.find(book => String(book.id) === String(id))
  return <LibraryContext.Provider value={{ books, updateStatus, addBook, getBook }}>{children}</LibraryContext.Provider>
}

// Este archivo exporta deliberadamente el proveedor y su hook de acceso.
// eslint-disable-next-line react-refresh/only-export-components
export function useLibrary() {
  const context = useContext(LibraryContext)
  if (!context) throw new Error('useLibrary debe utilizarse dentro de LibraryProvider')
  return context
}
