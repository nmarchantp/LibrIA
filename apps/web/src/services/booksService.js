import { apiRequest } from '../api/client'
import { displayBookEdition, displayBookTitle } from '../utils/bookTitles.js'

export function normalizeGoogleBook(item) {
  if (!item || typeof item !== 'object' || typeof item.id !== 'string' || !item.id.trim()) return null
  const info = item.volumeInfo && typeof item.volumeInfo === 'object' ? item.volumeInfo : {}
  const text = (value, fallback = '') => typeof value === 'string' ? value : fallback
  const list = value => Array.isArray(value) ? value.filter(entry => typeof entry === 'string') : []
  const authorNames = list(info.authors)
  const identifiers = Object.fromEntries((Array.isArray(info.industryIdentifiers) ? info.industryIdentifiers : []).filter(value => value && typeof value.type === 'string' && typeof value.identifier === 'string').map(value => [value.type, value.identifier]))
  const authors = authorNames.length ? authorNames.join(', ') : 'Autor desconocido'
  const firstPublicationDate = item.libria?.originalPublicationVerified ? text(item.libria?.firstPublicationDate) : ''
  const year = firstPublicationDate ? Number(firstPublicationDate.slice(0, 4)) : undefined
  const originalTitle = text(info.title, 'Sin título')
  const title = displayBookTitle(originalTitle, info.language)

  return {
    id: item.libria?.workId ?? item.id,
    externalId: item.libria?.externalId ?? item.id,
    workId: item.libria?.workId ?? null,
    editionId: item.libria?.editionId ?? null,
    editionCount: item.libria?.editionCount ?? 1,
    editions: (Array.isArray(item.libria?.editions) ? item.libria.editions : []).map(displayBookEdition),
    readingStats: item.libria?.readingStats ?? { finished: 0, reading: 0, abandoned: 0, readerPreview: [] },
    catalogOrigin: item.libria?.catalogOrigin === 'open_library' ? 'libria' : item.libria?.catalogOrigin ?? 'google_books',
    sourceProvider: item.libria?.catalogOrigin ?? 'google_books',
    rawVolume: item,
    originalTitle,
    title,
    subtitle: text(info.subtitle, ''),
    author: authors,
    authors: authorNames,
    year,
    publishedDate: text(info.publishedDate),
    description: text(info.description, 'Resultado obtenido desde Google Books.'),
    pageCount: info.pageCount ?? null,
    categories: list(info.categories),
    language: text(info.language, 'es'),
    publisher: text(info.publisher, 'Editorial desconocida'),
    isbn: identifiers.ISBN_13 ?? identifiers.ISBN_10 ?? '',
    previewLink: info.previewLink ?? '',
    canonicalVolumeLink: info.canonicalVolumeLink ?? '',
    printType: text(info.printType, 'BOOK'),
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
    image: text(info.imageLinks?.thumbnail, text(info.imageLinks?.smallThumbnail)).replace(/^http:/, 'https:') || null,
  }
}

export async function searchGoogleBooks(query) {
  const q = query?.trim()
  const data = await apiRequest(`/books?q=${encodeURIComponent(q || '')}`)
  return (Array.isArray(data.items) ? data.items : []).map(normalizeGoogleBook).filter(Boolean)
}

export async function searchBookCatalog(query, searchBy = 'all', { signal, refresh = false, startIndex = 0, provider = 'google_books', page = 1 } = {}) {
  const params = new URLSearchParams({ q: query?.trim() || '', search_by: searchBy })
  if (refresh) params.set('refresh', 'true')
  if (startIndex) params.set('start_index', String(startIndex))
  if (provider !== 'google_books') { params.set('provider', provider); params.set('page', String(page)) }
  const data = await apiRequest(`/books?${params}`, { signal, cache: 'no-store' })
  return { books: (Array.isArray(data.items) ? data.items : []).map(normalizeGoogleBook).filter(Boolean),
    warning: data.warning || '', hasMore: Boolean(data.has_more), nextStartIndex: data.next_start_index ?? 0,
    provider: data.active_provider || provider, nextPage: data.next_page ?? 1 }
}

export async function getGoogleBookById(id) {
  if (!id) return null
  const item = await apiRequest(`/books/${encodeURIComponent(id)}`, { cache: 'no-store' })
  return normalizeGoogleBook(item)
}
