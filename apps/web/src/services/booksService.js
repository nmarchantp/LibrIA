const GOOGLE_BOOKS_URL = 'https://www.googleapis.com/books/v1/volumes'

function normalizeGoogleBook(item) {
  const info = item?.volumeInfo ?? {}
  const authors = Array.isArray(info.authors) ? info.authors.join(', ') : 'Autor desconocido'
  const year = info.publishedDate ? Number(info.publishedDate.slice(0, 4)) : undefined
  const title = info.title ?? 'Sin título'

  return {
    id: item?.id ?? `${Date.now()}-${Math.random()}`,
    title,
    subtitle: info.subtitle ?? '',
    author: authors,
    authors: info.authors ?? [],
    year,
    publishedDate: info.publishedDate ?? '',
    description: info.description ?? 'Resultado obtenido desde Google Books.',
    pageCount: info.pageCount ?? null,
    categories: info.categories ?? [],
    language: info.language ?? 'es',
    publisher: info.publisher ?? 'Editorial desconocida',
    previewLink: info.previewLink ?? '',
    canonicalVolumeLink: info.canonicalVolumeLink ?? '',
    printType: info.printType ?? 'BOOK',
    averageRating: info.averageRating ?? null,
    ratingsCount: info.ratingsCount ?? null,
    maturityRating: info.maturityRating ?? '',
    infoLink: info.infoLink ?? '',
    canonicalVolumeLink: info.canonicalVolumeLink ?? '',
    status: null,
    progress: 0,
    color: '#173f35',
    accent: '#ffb65c',
    initial: title.trim().charAt(0).toUpperCase() || 'L',
    image: info.imageLinks?.thumbnail ?? info.imageLinks?.smallThumbnail ?? null,
  }
}

export async function searchGoogleBooks(query) {
  const apiKey = import.meta.env.VITE_GOOGLE_BOOKS_API_KEY
  const q = query?.trim()

  if (!apiKey || !q) return []

  const url = `${GOOGLE_BOOKS_URL}?q=${encodeURIComponent(q)}&maxResults=12&key=${encodeURIComponent(apiKey)}`
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error('No fue posible consultar Google Books')
  }

  const data = await response.json()
  return (data.items ?? []).map(normalizeGoogleBook)
}

export async function getGoogleBookById(id) {
  const apiKey = import.meta.env.VITE_GOOGLE_BOOKS_API_KEY
  if (!id || !apiKey) return null

  const url = `${GOOGLE_BOOKS_URL}/${encodeURIComponent(id)}?key=${encodeURIComponent(apiKey)}`
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error('No fue posible cargar la información del libro')
  }

  const item = await response.json()
  return normalizeGoogleBook(item)
}
