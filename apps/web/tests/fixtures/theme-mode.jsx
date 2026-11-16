import React from 'react'
import { createRoot } from 'react-dom/client'
import { ThemeProvider } from '../../src/context/ThemeContext'
import ThemeModeToggle from '../../src/components/ThemeModeToggle'
import '../../src/styles.css'
import '../../src/theme/themes.css'
import '../../src/components/LayoutNavigation.css'
if(new URLSearchParams(location.search).has('reset')) { localStorage.removeItem('libria_theme'); history.replaceState({},'',location.pathname) }
createRoot(document.getElementById('root')).render(<ThemeProvider><nav className="global-header-actions"><ThemeModeToggle /></nav></ThemeProvider>)
