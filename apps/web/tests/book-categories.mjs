import assert from 'node:assert/strict'
import { normalizeBookCategories, presentBookCategories } from '../src/components/bookCategories.js'

const original = [
  'Juvenile Fiction / Action & Adventure / General',
  'Young Adult Fiction / Classics',
  'Fiction / Christian / Fantasy',
  'Juvenile Fiction / Religious / Christian / Action & Adventure',
]
assert.deepEqual(normalizeBookCategories(original), [
  'Juvenile Fiction', 'Action & Adventure', 'General', 'Young Adult Fiction',
  'Classics', 'Fiction', 'Christian', 'Fantasy', 'Religious',
])
assert.equal(original[0], 'Juvenile Fiction / Action & Adventure / General')
assert.deepEqual(normalizeBookCategories([' Fantasy / / fantasy ', 'Young   Adult Fiction'],
  [{ name: 'young adult fiction / Romance' }, null, {}]), ['Fantasy', 'Young Adult Fiction', 'Romance'])
assert.deepEqual(normalizeBookCategories([], []), [])
assert.deepEqual(presentBookCategories(['Fantasy / Fantasía / FANTASY', 'Juvenile Fiction / Young Adult Fiction', 'Unknown Proper Name']).map(({ label, family }) => [label, family]), [
  ['Fantasía', 'fantasy'], ['Ficción juvenil', 'young'], ['Literatura juvenil', 'young'], ['Unknown Proper Name', 'neutral'],
])
assert.equal(presentBookCategories(original).length, 9)
assert.equal(presentBookCategories(['Romance'])[0].original, 'Romance')
console.log('Book category normalization: passed')
