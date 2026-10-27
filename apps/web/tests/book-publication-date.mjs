// Exercise the actual normalizer without Vite or any API/network requests.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('../src/services/booksService.js', import.meta.url), 'utf8')
const withTitleUtility = source.replace("'../utils/bookTitles.js'", JSON.stringify(new URL('../src/utils/bookTitles.js', import.meta.url).href))
const isolated = withTitleUtility.replace("import { apiRequest } from '../api/client'", 'const apiRequest = () => { throw new Error("Unexpected API request") }')
const { normalizeGoogleBook } = await import(`data:text/javascript;base64,${Buffer.from(isolated).toString('base64')}`)
const item = { id: 'test-work', volumeInfo: { title: 'Test', publishedDate: '2015-11-19' } }

assert.equal(normalizeGoogleBook(item).year, undefined)
assert.equal(normalizeGoogleBook({ ...item, libria: { firstPublicationDate: '1843' } }).year, undefined)
assert.equal(normalizeGoogleBook({ ...item, libria: { firstPublicationDate: '1843', originalPublicationVerified: false } }).year, undefined)
const verified = normalizeGoogleBook({ ...item, libria: { firstPublicationDate: '2005', originalPublicationVerified: true } })
assert.equal(verified.year, 2005)
assert.equal(verified.publishedDate, '2015-11-19')
console.log('Publication date: 5 assertions passed; no API requests')
