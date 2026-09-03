import { createContext, useContext, useState } from 'react'
import { books as initialBooks } from '../data'

const LibraryContext = createContext(null)

// Centraliza temporalmente la biblioteca; luego sus acciones llamarán a FastAPI.
export function LibraryProvider({ children }) {
  const [books, setBooks] = useState(initialBooks)
  const updateStatus = (id, status) => setBooks(current => current.map(book => book.id === Number(id) ? { ...book, status } : book))
  const getBook = (id) => books.find(book => book.id === Number(id))
  return <LibraryContext.Provider value={{ books, updateStatus, getBook }}>{children}</LibraryContext.Provider>
}

// Este archivo exporta deliberadamente el proveedor y su hook de acceso.
// eslint-disable-next-line react-refresh/only-export-components
export function useLibrary() {
  const context = useContext(LibraryContext)
  if (!context) throw new Error('useLibrary debe utilizarse dentro de LibraryProvider')
  return context
}
