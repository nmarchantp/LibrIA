// Stable IDs can also identify future theme assets without changing consumers.
export const themes = [
  { id: 'lavanda', name: 'Jardín de Macarons', group: 'light', colors: ['#F4EFF9', '#FFFCFF', '#7856A4', '#DFD1EF', '#B38BCD', '#332743'] },
  { id: 'otono', name: 'Tintas del Equinoccio', group: 'light', colors: ['#F7EDE1', '#FFFAF4', '#A75D43', '#E9C5A6', '#B58A4D', '#443128'] },
  { id: 'invierno', name: 'Alas de Cristal', group: 'light', colors: ['#EAF1F5', '#FAFCFF', '#496E91', '#C5DCE9', '#789BAE', '#263A50'] },
  { id: 'rosa-antiguo', name: 'Algodón de azúcar', group: 'light', colors: ['#F9EFF0', '#FFF9F7', '#A7657D', '#EED1D8', '#C997A4', '#513442'] },
  { id: 'bosque', name: 'Bosque feérico', group: 'light', colors: ['#EDF1E8', '#FCFCF5', '#56755F', '#C9D8BD', '#A1A77A', '#2E4335'] },
  { id: 'dark', name: 'Reino de Sombras', group: 'dark', colors: ['#181721', '#292535', '#C2A4F3', '#453854', '#9776CF', '#F6F0FC'] },
  { id: 'dark-rosado', name: 'Rosas y Espinas', group: 'dark', colors: ['#1C161E', '#382936', '#E8A0C2', '#30232F', '#B876A0', '#F7EAF1'] },
  { id: 'dark-blood', name: 'Pacto de Sangre', group: 'dark', colors: ['#050507', '#1D1D24', '#89001F', '#480014', '#C4183D', '#F5EDF0'], roles: { primary: '#EE7893' } },
  { id: 'dark-dorado', name: 'Biblioteca de Medianoche', group: 'dark', colors: ['#141416', '#2C2B2D', '#E2C17A', '#202023', '#B89550', '#F5F0E5'] },
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
  // Preserve the reference palette; optional roles supply accessible variants
  // (Blood uses a luminous red for small text/SVGs, wine red for filled buttons).
  ;['paper', 'surface', 'primary', 'secondary', 'accent', 'ink'].forEach((role, index) => {
    root.style.setProperty(`--${role}`, theme.roles?.[role] ?? theme.colors[index])
  })
  root.dataset.theme = theme.id
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme.colors[0])
}
