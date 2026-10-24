import { apiRequest } from '../api/client'

export function normalizeGoogleBook(item) {
  const info = item?.volumeInfo ?? {}
  const identifiers = Object.fromEntries((info.industryIdentifiers ?? []).map(value => [value.type, value.identifier]))
  const authors = Array.isArray(info.authors) ? info.authors.join(', ') : 'Autor desconocido'
  const firstPublicationDate = item.libria?.firstPublicationDate ?? info.publishedDate ?? ''
  const year = firstPublicationDate ? Number(firstPublicationDate.slice(0, 4)) : undefined
  const title = info.title ?? 'Sin título'

  return {
    id: item.libria?.workId ?? item.id,
    externalId: item.libria?.externalId ?? item.id,
    workId: item.libria?.workId ?? null,
    editionId: item.libria?.editionId ?? null,
    editionCount: item.libria?.editionCount ?? 1,
    editions: item.libria?.editions ?? [],
    readingStats: item.libria?.readingStats ?? { finished: 0, reading: 0, abandoned: 0, readerPreview: [] },
    catalogOrigin: item.libria?.catalogOrigin ?? 'google_books',
    rawVolume: item,
    title,
    subtitle: info.subtitle ?? '',
    author: authors,
    authors: info.authors ?? [],
    year,
    publishedDate: info.publishedDate ?? firstPublicationDate,
    description: info.description ?? 'Resultado obtenido desde Google Books.',
    pageCount: info.pageCount ?? null,
    categories: info.categories ?? [],
    language: info.language ?? 'es',
    publisher: info.publisher ?? 'Editorial desconocida',
    isbn: identifiers.ISBN_13 ?? identifiers.ISBN_10 ?? '',
    previewLink: info.previewLink ?? '',
    canonicalVolumeLink: info.canonicalVolumeLink ?? '',
    printType: info.printType ?? 'BOOK',
    averageRating: item.libria?.averageRating ?? null,
    ratingsCount: item.libria?.ratingsCount ?? null,
    maturityRating: info.maturityRating ?? '',
    infoLink: info.infoLink ?? '',
    canonicalVolumeLink: info.canonicalVolumeLink ?? '',
    status: null,
    progress: 0,
    color: '#173f35',
    accent: '#ffb65c',
    initial: title.trim().charAt(0).toUpperCase() || 'L',
    image: (info.imageLinks?.thumbnail ?? info.imageLinks?.smallThumbnail ?? '').replace(/^http:/, 'https:') || null,
  }
}

export async function searchGoogleBooks(query) {
  const q = query?.trim()
  const data = await apiRequest(`/books?q=${encodeURIComponent(q || '')}`)
  return (data.items ?? []).map(normalizeGoogleBook)
}

export async function searchBookCatalog(query, searchBy = 'all') {
  const data = await apiRequest(`/books?q=${encodeURIComponent(query?.trim() || '')}&search_by=${encodeURIComponent(searchBy)}`)
  return { books: (data.items ?? []).map(normalizeGoogleBook), warning: data.warning || '' }
}

export async function getGoogleBookById(id) {
  if (!id) return null
  const item = await apiRequest(`/books/${encodeURIComponent(id)}`, { cache: 'no-store' })
  return normalizeGoogleBook(item)
}
