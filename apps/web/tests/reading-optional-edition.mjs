import assert from 'node:assert/strict'
import { librarySelection } from '../src/services/librarySelection.js'
import { withReading, eventPageCount } from '../src/services/readingState.js'

const book = { id: 'work', workId: 'work', title: 'Obra', editionOptional: true, catalogFlow: 'discovery-v1',
  editionId: 'shown-edition', pageCount: 237 }
assert.equal(librarySelection(book).edition_id, null)
assert.equal(librarySelection(book).edition_selected, false)
assert.equal(librarySelection({ ...book, editionExplicit: true }).edition_id, 'shown-edition')
const state = { reading_id: 'attempt', work_id: 'work', edition_id: null, edition_optional: true,
  status: 'reading', current_page: 17, total_pages: null, progress_percent: null }
const restored = withReading(book, state)
assert.equal(restored.editionId, null)
assert.equal(restored.pageCount, null)
assert.equal(restored.bibliographicPageCount, 237)
assert.equal(restored.progress, null)
assert.equal(eventPageCount(restored), null)
assert.equal(eventPageCount(restored, { page_count: 80 }), 80)
assert.throws(() => eventPageCount(restored, { page_count: -1 }))
const selectedLater = withReading(book, { ...state, edition_id: 'chosen' })
assert.equal(selectedLater.editionId, 'chosen')
assert.equal(selectedLater.currentPage, 17)
assert.equal(selectedLater.pageCount, null)
assert.equal(withReading(book, { ...state, edition_optional: false }).pageCount, 237)
assert.equal(librarySelection({ ...book, workId: null, editionId: null, selectionReference: {
  provider: 'google-books', reference_type: 'volume', external_id: 'publication' },
}).edition_selected, false)
console.log('Optional edition: selections, reload, unknown totals, declared totals, later selection and legacy compatibility OK')
