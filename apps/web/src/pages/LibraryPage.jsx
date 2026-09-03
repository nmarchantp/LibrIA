import { useState } from 'react'
import { Link } from 'react-router-dom'
import BookCover from '../components/BookCover'
import { useLibrary } from '../context/LibraryContext'

export default function LibraryPage(){const{books,updateStatus}=useLibrary();const[filter,setFilter]=useState('Todos');const shown=filter==='Todos'?books:books.filter(b=>b.status===filter);return <section className="page-width page"><span className="kicker">TU RECORRIDO LECTOR</span><h1 className="page-title">Mi biblioteca</h1><div className="tabs">{['Todos','Leyendo','Pendiente','Terminado'].map(item=><button className={filter===item?'active':''} onClick={()=>setFilter(item)} key={item}>{item}</button>)}</div><div className="library-list">{shown.map(book=><article className="library-row" key={book.id}><Link to={`/books/${book.id}`}><BookCover book={book}/></Link><div className="library-details"><h2>{book.title}</h2><p>{book.author}</p></div><select value={book.status} onChange={e=>updateStatus(book.id,e.target.value)}><option>Leyendo</option><option>Pendiente</option><option>Terminado</option><option>Abandonado</option></select></article>)}</div></section>}
