// Explicit, reliable translations only; unknown labels retain their catalog name.
export const bookCategoryDictionary = {
  'juvenile fiction': { label: 'Ficción juvenil', family: 'young' },
  'young adult fiction': { label: 'Literatura juvenil', family: 'young' },
  'action & adventure': { label: 'Acción y aventura', family: 'adventure' },
  fantasy: { label: 'Fantasía', family: 'fantasy' },
  magic: { label: 'Magia', family: 'fantasy' },
  'science fiction': { label: 'Ciencia ficción', family: 'scifi' },
  mystery: { label: 'Misterio', family: 'mystery' },
  suspense: { label: 'Suspenso', family: 'mystery' },
  thriller: { label: 'Thriller', family: 'mystery' },
  horror: { label: 'Terror', family: 'horror' },
  classics: { label: 'Clásicos', family: 'classics' },
  fiction: { label: 'Ficción', family: 'fiction' },
  general: { label: 'General', family: 'neutral' },
  romance: { label: 'Romance', family: 'romance' },
  'historical fiction': { label: 'Ficción histórica', family: 'historical' },
  christian: { label: 'Cristiano', family: 'neutral' },
  religious: { label: 'Religioso', family: 'neutral' },
}

const categoryKey = value => value.replace(/\s+/g, ' ').trim().toLocaleLowerCase('es')
const localizedCategories = new Map(Object.values(bookCategoryDictionary).map(category => [categoryKey(category.label), category]))

// Returns display metadata without modifying catalog categories, search or filters.
export function presentBookCategories(...sources) {
  const seen = new Set()
  return normalizeBookCategories(...sources).flatMap(original => {
    const key = categoryKey(original)
    const category = bookCategoryDictionary[key] || localizedCategories.get(key) || { label: original, family: 'neutral' }
    const displayKey = categoryKey(category.label)
    if (seen.has(displayKey)) return []
    seen.add(displayKey)
    return [{ ...category, original }]
  })
}

// Presentation only: preserve catalog values and their order at the source.
export function normalizeBookCategories(...sources) {
  const seen = new Set()
  const categories = []
  for (const item of sources.flat()) {
    const name = typeof item === 'string' ? item : item?.name
    if (typeof name !== 'string') continue
    for (const part of name.split('/')) {
      const label = part.replace(/\s+/g, ' ').trim()
      const key = label.toLocaleLowerCase('en')
      if (!label || seen.has(key)) continue
      seen.add(key)
      categories.push(label)
    }
  }
  return categories
}
