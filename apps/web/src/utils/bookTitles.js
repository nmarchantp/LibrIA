// Presentation only. Never use these labels as bibliographic identity keys.
const comparable = value => value.normalize('NFD').replace(/\p{M}/gu, '').toLocaleLowerCase('es').replace(/\s+/g, ' ').trim()
const spanishLanguages = new Set(['es', 'spa', 'spanish', 'español'])

// Explicit parallel titles confirmed by catalog examples. Unknown pairs stay intact:
// language guessing alone cannot distinguish a translation from an authentic title.
const parallelTitles = [
  {
    spanish: 'el infinito en un junco',
    english: new Set(['papyrus', 'papyrus: the invention of books', 'papyrus: the invention of books in the ancient world',
      'papyrus: the inven tion of books']),
  },
]
const editionLabels = new Map([
  ['adaptacion grafica', 'graphic adaptation'],
  ['edicion limitada', 'limited edition'],
  ['edicion limitada firmada', 'signed limited edition'],
  ['edicion limitada cantos pintados', 'limited sprayed edges edition'],
  ['cantos pintados', 'sprayed edges'],
  ['edicion ilustrada', 'illustrated edition'],
  ['edicion especial', 'special edition'],
])

function parts(value, allowIncompleteEdition = false) {
  const match = /^(.*?)\s*\(([^()]*)\)\s*$/.exec(value) ||
    (allowIncompleteEdition && /^(.*?)\s*\(([^()]*)$/.exec(value))
  return match ? { base: match[1].trim(), edition: match[2] } : { base: value.trim(), edition: '' }
}

function editionKeys(value) {
  return value ? value.split(',').map(comparable) : []
}

export function displayBookTitle(originalTitle, language, { preserveBilingual = false } = {}) {
  if (typeof originalTitle !== 'string') return ''
  if (preserveBilingual || !spanishLanguages.has(String(language || '').toLowerCase().split('-')[0])) return originalTitle
  const halves = originalTitle.split(/\s+\/\s+/)
  if (halves.length !== 2) return originalTitle
  const spanish = parts(halves[0])
  // Some providers truncate the English edition note after an opening bracket.
  // This only helps identify a known parallel base; it never edits the source.
  const english = parts(halves[1], true)
  const spanishEdition = editionKeys(spanish.edition)
  const englishEdition = editionKeys(english.edition)
  const knownPair = parallelTitles.some(pair => pair.spanish === comparable(spanish.base) && pair.english.has(comparable(english.base)))
  const knownEditionPair = spanishEdition.length > 0 && spanishEdition.every(key => editionLabels.has(key)) &&
    englishEdition.length === spanishEdition.length &&
    spanishEdition.every((key, index) => editionLabels.get(key) === englishEdition[index])
  // Same base + explicitly translated edition descriptors is also unambiguous.
  if (!knownPair && !(comparable(spanish.base) === comparable(english.base) && knownEditionPair)) return originalTitle
  // For known parallel titles, retain unfamiliar parentheses verbatim too.
  const base = knownPair ? spanish.base.charAt(0).toLocaleUpperCase('es') + spanish.base.slice(1).toLocaleLowerCase('es') : spanish.base
  const edition = spanishEdition.length && spanishEdition.every(key => editionLabels.has(key))
    ? spanish.edition.toLocaleLowerCase('es') : spanish.edition
  return edition ? `${base} (${edition})` : base
}

export function displayBookEdition(edition) {
  if (!edition || typeof edition !== 'object') return edition
  const originalTitle = edition.originalTitle ?? edition.title
  return { ...edition, originalTitle, title: displayBookTitle(originalTitle, edition.language) }
}
