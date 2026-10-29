import assert from 'node:assert/strict'
import { librarySelection } from '../src/services/librarySelection.js'

const ref = { provider: 'google-books', reference_type: 'volume', external_id: 'volume-1' }
const external = { id: 'volume-1', title: 'Display title', catalogFlow: 'discovery-v1', selectionReference: ref }
assert.deepEqual(librarySelection(external), { book_ref: 'volume-1', book_title: 'Display title', edition_id: null,
  page_count: null, external_reference: ref, edition_selected: true })
const local = librarySelection({ ...external, id: 'work-1', workId: 'work-1', editionId: 'edition-2' })
assert.equal(local.edition_id, 'edition-2')
assert.equal(local.book_ref, 'work-1')
assert.equal(local.external_reference, undefined)
assert.equal(local.edition_selected, true)
assert.throws(() => librarySelection({ ...external, selectionReference: null }), /Selecciona una edición/)
assert.equal(librarySelection({ id: 'legacy', title: 'Old book' }).edition_selected, undefined)
console.log('Library selections: external publication, explicit internal edition, missing selection, legacy compatibility OK')
