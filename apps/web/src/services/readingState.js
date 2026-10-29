const statusLabels = { pending: 'Pendiente', reading: 'Leyendo', finished: 'Terminado', abandoned: 'Abandonado' }

export const withReading = (book, reading) => reading ? {
  ...book, status: statusLabels[reading.status] || book.status,
  progress: reading.progress_percent, currentPage: reading.current_page,
  bibliographicPageCount: book.bibliographicPageCount ?? book.pageCount ?? null,
  pageCount: reading.edition_optional ? reading.total_pages : reading.total_pages ?? book.pageCount,
  editionOptional: Boolean(reading.edition_optional), readingId: reading.reading_id,
  workId: reading.work_id, editionId: reading.edition_id,
  reflection: reading.reflection, startedAt: reading.started_at, finishedAt: reading.finished_at,
  notebook: reading.notebook || {},
} : book

export function eventPageCount(book, extra = {}) {
  const raw = extra.page_count ?? book.pageCount
  if (book.editionOptional && (raw == null || raw === '')) return null
  const total = Number(raw)
  if (!Number.isInteger(total) || total < 1 || total > 100000) throw new Error('Indica un total de páginas válido para esta lectura.')
  return total
}
