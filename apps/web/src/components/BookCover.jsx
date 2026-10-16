import { useEffect, useState } from 'react'

export default function BookCover({ book, large = false }) {
  const [imageFailed, setImageFailed] = useState(false)
  const hasImage = Boolean(book?.image) && !imageFailed

  useEffect(() => { setImageFailed(false) }, [book?.image])

  return (
    <div
      className={`book-cover ${large ? 'book-cover--large' : ''}`}
      style={{ background: book.color || '#605680', color: book.accent || '#ffffff' }}
      aria-label={`Portada de ${book.title}`}
    >
      {hasImage && <img className="book-cover-image" src={book.image} alt="" onError={() => setImageFailed(true)} />}
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
