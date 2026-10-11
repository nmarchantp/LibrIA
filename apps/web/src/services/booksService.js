import { apiRequest } from '../api/client'

export function normalizeGoogleBook(item) {
  const info = item?.volumeInfo ?? {}
  const authors = Array.isArray(info.authors) ? info.authors.join(', ') : 'Autor desconocido'
  const year = info.publishedDate ? Number(info.publishedDate.slice(0, 4)) : undefined
  const title = info.title ?? 'Sin título'

  return {
    id: item.id,
    rawVolume: item,
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
  const q = query?.trim()
  const data = await apiRequest(`/books?q=${encodeURIComponent(q || '')}`)
  return (data.items ?? []).map(normalizeGoogleBook)
}

export async function searchBookCatalog(query) {
  const data = await apiRequest(`/books?q=${encodeURIComponent(query?.trim() || '')}`)
  return { books: (data.items ?? []).map(normalizeGoogleBook), warning: data.warning || '' }
}

export async function getGoogleBookById(id) {
  if (!id) return null
  const item = await apiRequest(`/books/${encodeURIComponent(id)}`)
  return normalizeGoogleBook(item)
}
