// References/UUIDs are selections. Titles, authors and ISBNs are never evidence.
export function librarySelection(book) {
  const legacy = { book_ref: String(book.id), book_title: book.originalTitle || book.title,
    edition_id: book.editionId || null, page_count: book.pageCount || null }
  if (book.catalogFlow !== 'discovery-v1') return legacy
  if (book.editionOptional && !book.editionExplicit) {
    if (book.workId) return { ...legacy, book_ref: String(book.workId), edition_id: null, page_count: null, edition_selected: false }
    if (book.selectionReference) return { ...legacy, edition_id: null, page_count: null, external_reference: book.selectionReference, edition_selected: false }
  }
  if (book.workId && book.editionId) return { ...legacy, book_ref: String(book.workId), edition_selected: true }
  if (!book.selectionReference) throw new Error('Selecciona una edición antes de agregar el libro.')
  return { ...legacy, edition_id: null, external_reference: book.selectionReference, edition_selected: true }
}
