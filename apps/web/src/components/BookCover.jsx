// Portada temporal generada con texto hasta integrar una API bibliográfica.
export default function BookCover({ book, large = false }) {
  return <div className={`book-cover ${large ? 'book-cover--large' : ''}`} style={{ background: book.color, color: book.accent }} aria-label={`Portada de ${book.title}`}>
    <span className="cover-mark">{book.initial}</span><span className="cover-title">{book.title}</span><span className="cover-author">{book.author}</span>
  </div>
}
