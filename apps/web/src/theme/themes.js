// Stable IDs can also identify future theme assets without changing consumers.
export const themes = [
  { id: 'lavanda', name: 'Lavanda', colors: ['#F4EFF9', '#FFFCFF', '#7856A4', '#DFD1EF', '#B38BCD', '#332743'] },
  { id: 'otono', name: 'Otoño', colors: ['#F7EDE1', '#FFFAF4', '#A75D43', '#E9C5A6', '#B58A4D', '#443128'] },
  { id: 'invierno', name: 'Invierno', colors: ['#EAF1F5', '#FAFCFF', '#496E91', '#C5DCE9', '#789BAE', '#263A50'] },
  { id: 'dark', name: 'Dark', colors: ['#181721', '#292535', '#C2A4F3', '#453854', '#9776CF', '#F6F0FC'] },
  { id: 'bosque', name: 'Bosque', colors: ['#EDF1E8', '#FCFCF5', '#56755F', '#C9D8BD', '#A1A77A', '#2E4335'] },
  { id: 'rosa-antiguo', name: 'Rosa antiguo', colors: ['#F9EFF0', '#FFF9F7', '#A7657D', '#EED1D8', '#C997A4', '#513442'] },
]

export const themeStorageKey = 'libria_theme'
export const defaultTheme = 'lavanda'
export const validTheme = value => themes.some(theme => theme.id === value)

export function readTheme() {
  try {
    const saved = localStorage.getItem(themeStorageKey)
    return validTheme(saved) ? saved : defaultTheme
  } catch { return defaultTheme }
}

export function applyTheme(id) {
  const theme = themes.find(item => item.id === id) || themes[0]
  const root = document.documentElement
  // Set the exact palette centrally; CSS derives accessible semantic roles.
  ;['paper', 'surface', 'primary', 'secondary', 'accent', 'ink'].forEach((role, index) => {
    root.style.setProperty(`--${role}`, theme.colors[index])
  })
  root.dataset.theme = theme.id
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme.colors[0])
}
