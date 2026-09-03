import { Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import BookCover from '../components/BookCover'
import { useLibrary } from '../context/LibraryContext'

export default function BooksPage(){const{books}=useLibrary();const[query,setQuery]=useState('');const visible=useMemo(()=>books.filter(b=>`${b.title} ${b.author}`.toLowerCase().includes(query.toLowerCase())),[books,query]);return <section className="page-width page"><span className="kicker">ENCUENTRA TU PRÓXIMA LECTURA</span><h1 className="page-title">Explora nuevos mundos</h1><label className="search-box"><Search/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Buscar libros o autores…"/></label><div className="result-line"><strong>{visible.length} libros</strong></div><div className="book-grid">{visible.map(book=><Link className="book-tile" to={`/books/${book.id}`} key={book.id}><BookCover book={book}/><span className="pill">{book.status}</span><h3>{book.title}</h3><p>{book.author} · {book.year}</p></Link>)}</div></section>}
