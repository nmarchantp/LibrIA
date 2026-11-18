import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider, useTheme } from '/src/context/ThemeContext'
import { AuthProvider } from '/src/context/AuthContext'
import { LibraryProvider } from '/src/context/LibraryContext'
import InitialLiteraryDNA from '/src/components/InitialLiteraryDNA'
import { onboardingService } from '/src/services/onboardingService'
import '/src/styles.css'
import '/src/pages/ProfilePage.css'

localStorage.clear()
localStorage.setItem('libriaverse-magical-background', 'true')
localStorage.setItem('libriaverse-magical-background-motion', 'true')
const initial = { status: 'completed', ai_status: 'completed', recommendations: Array.from({ length: 5 }, (_, index) => ({ work_id: `book-${index}`, title: `Libro ${index + 1}`, authors: ['Autora'] })) }
onboardingService.get = async () => initial
onboardingService.syncFavorites = async () => ({})
// eslint-disable-next-line react-refresh/only-export-components
function Demo() {
  const { setMagicalBackgroundMotion } = useTheme()
  return <><button id="motion" onClick={() => setMagicalBackgroundMotion(value => !value)}>Mover los puntitos</button><InitialLiteraryDNA compact initial={initial} /></>
}
createRoot(document.getElementById('root')).render(<MemoryRouter><ThemeProvider><AuthProvider><LibraryProvider><Demo /></LibraryProvider></AuthProvider></ThemeProvider></MemoryRouter>)
