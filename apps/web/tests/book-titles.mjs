import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { displayBookTitle, displayBookEdition } from '../src/utils/bookTitles.js'

const cases = [
  ['El Infinito en un Junco (Edición Limitada Firmada) / Papyrus: the Invention of Books in the Ancient World (', 'es', 'El infinito en un junco (edición limitada firmada)'],
  ['El Infinito en un Junco (Edición Limitada Firmada) / Papyrus: the Invention of Books in the Ancient World (Signed limited', 'es', 'El infinito en un junco (edición limitada firmada)'],
  ['Vida / Una historia (', 'es'],
  ['El infinito en un junco / Papyrus: otro relato (', 'es'],
  ['El Infinito En Un Junco / Papyrus: The Invention of Books in the Ancient World', 'es', 'El infinito en un junco'],
  ['El Infinito En Un Junco (Adaptación Gráfica) / Papyrus: The Invention of Books in the Ancient World', 'es', 'El infinito en un junco (adaptación gráfica)'],
  ['El Infinito En Un Junco (Adaptación Gráfica) / Papyrus (Graphic adaptation)', 'spa', 'El infinito en un junco (adaptación gráfica)'],
  ['El Infinito En Un Junco (Edición Limitada, Cantos Pintados) / Papyrus: The Invention of Books (Limited Edition, Sprayed Edges)', 'es', 'El infinito en un junco (edición limitada, cantos pintados)'],
  ['El Infinito En Un Junco (Edición Limitada, Cantos Pintados) / Papyrus: The Inven Tion of Books (Limited Edition, Sprayed Edges)', 'es', 'El infinito en un junco (edición limitada, cantos pintados)'],
  ['El Infinito en un Junco (edición Limitada Cantos Pintados) / Papyrus (Limited Sprayed Edges Edition)', 'es', 'El infinito en un junco (edición limitada cantos pintados)'],
  ['El infinito en un junco (Edición Ilustrada) / Papyrus (Illustrated Edition)', 'es-CL', 'El infinito en un junco (edición ilustrada)'],
  ['El infinito en un junco (Edición Especial) / Papyrus (Special Edition)', 'es', 'El infinito en un junco (edición especial)'],
  ['La novela (Adaptación gráfica) / La novela (Graphic adaptation)', 'es', 'La novela (adaptación gráfica)'],
  ['Papyrus: The Invention of Books in the Ancient World', 'es'],
  ['El infinito en un junco / Papyrus', 'en'],
  ['El infinito en un junco / Papyrus', undefined],
  ['Vida / muerte: dos relatos', 'es'],
  ['Madrid / Barcelona (edición especial)', 'es'],
  ['El mar / The Sea: poemas bilingües', 'es'],
  ['El arte de vivir / The Art of Living', 'es'],
  ['Rayuela / Hopscotch: edición bilingüe', 'es'],
  ['La novela: el regreso (volumen 2)', 'es'],
  ['El infinito en un junco: una historia / Papyrus', 'es'],
  ['El infinito en un junco / Papyrus / notas', 'es'],
  ['El infinito en un junco (Prólogo de Irene Vallejo) / Papyrus', 'es', 'El infinito en un junco (Prólogo de Irene Vallejo)'],
]
for (const [original, language, expected = original] of cases) {
  assert.equal(displayBookTitle(original, language), expected, original)
}
assert.equal(displayBookTitle('El infinito en un junco / Papyrus', 'es', { preserveBilingual: true }), 'El infinito en un junco / Papyrus')

// Exercise the actual search/detail/library normalizer, stubbing only transport.
const source = await readFile(new URL('../src/services/booksService.js', import.meta.url), 'utf8')
const isolated = source
  .replace("import { apiRequest } from '../api/client'", 'const apiRequest = () => { throw new Error("Unexpected API request") }')
  .replace("'../utils/bookTitles.js'", JSON.stringify(new URL('../src/utils/bookTitles.js', import.meta.url).href))
const { normalizeGoogleBook } = await import(`data:text/javascript;base64,${Buffer.from(isolated).toString('base64')}`)
const original = cases[0][0]
const edition = { id: 'edition-id', title: original, language: 'es', isbn13: '9788417860790' }
const raw = { id: 'work-id', volumeInfo: { title: original, subtitle: 'Subtítulo real', language: 'es' }, libria: { editions: [edition] } }
const before = structuredClone(raw)
const book = normalizeGoogleBook(raw)
assert.equal(book.title, cases[0][2])
assert.equal(book.originalTitle, original)
assert.equal(book.subtitle, 'Subtítulo real')
assert.equal(book.rawVolume, raw)
assert.equal(book.editions[0].title, cases[0][2])
assert.equal(book.editions[0].originalTitle, original)
assert.equal(book.editions[0].id, edition.id)
assert.equal(book.editions[0].isbn13, edition.isbn13)
assert.deepEqual(raw, before)
assert.deepEqual(displayBookEdition(book.editions[0]), book.editions[0])
console.log(`Book titles: ${cases.length} title cases and 11 integration/provenance checks passed`)
