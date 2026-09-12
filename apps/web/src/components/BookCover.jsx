export default function BookCover({ book, large = false }) {
  const hasImage = Boolean(book?.image)

  return (
    <div
      className={`book-cover ${large ? 'book-cover--large' : ''}`}
      style={
        hasImage
          ? {
              backgroundImage: `url(${book.image})`,
              backgroundSize: 'cover',
              backgroundPosition: 'center',
              backgroundRepeat: 'no-repeat',
              color: '#fff',
            }
          : { background: book.color, color: book.accent }
      }
      aria-label={`Portada de ${book.title}`}
    >
      {!hasImage && (
        <>
          <span className="cover-mark">{book.initial}</span>
          <span className="cover-title">{book.title}</span>
          <span className="cover-author">{book.author}</span>
        </>
      )}
    </div>
  )
}
