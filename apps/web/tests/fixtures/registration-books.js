// Offline visual fixtures; these covers are never part of the real catalog.
const titles = [
  ['Orgullo y prejuicio', 'Jane Austen', '#5d426f', ['Orgullo', 'y prejuicio']],
  ['Alicia en el país de las maravillas', 'Lewis Carroll', '#376b79', ['Alicia', 'en el país de', 'las maravillas']],
  ['Frankenstein', 'Mary Shelley', '#3d6250', ['Frankenstein']],
  ['Mujercitas', 'Louisa May Alcott', '#974f67', ['Mujercitas']],
  ['Drácula', 'Bram Stoker', '#563945', ['Drácula']],
]

export const registrationBooks = titles.map(([title, author, color, lines], index) => {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="280" height="420" viewBox="0 0 280 420"><rect width="280" height="420" fill="${color}"/><rect x="14" y="14" width="252" height="392" rx="2" fill="none" stroke="#dfc793" stroke-width="2"/><rect x="22" y="22" width="236" height="376" fill="none" stroke="#dfc793" opacity=".4"/><path d="M140 60l12 34 36 3-28 23 9 35-29-20-29 20 9-35-28-23 36-3z" fill="none" stroke="#dfc793" stroke-width="2"/><text x="140" y="190" text-anchor="middle" fill="#fff3d6" font-family="Georgia,serif" font-size="25">${lines.map((line, row) => `<tspan x="140" dy="${row ? 32 : 0}">${line}</tspan>`).join('')}</text><path d="M70 310h140" stroke="#dfc793"/><text x="140" y="350" text-anchor="middle" fill="#dfc793" font-family="Georgia,serif" font-size="16">${author}</text></svg>`
  const id = `00000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`
  return { id, volumeInfo: { title, authors: [author], language: 'es', imageLinks: { thumbnail: `data:image/svg+xml,${encodeURIComponent(svg)}` } },
    libria: { workId: id, canonicalWorkId: id, editionOptional: true } }
})
