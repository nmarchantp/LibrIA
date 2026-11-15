import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '../../src/context/AuthContext'
import LoginPage from '../../src/pages/LoginPage'
import '../../src/styles.css'
import { applyTheme } from '../../src/theme/themes'
applyTheme('lavanda')
window.loginTest = { calls: [] }
window.fetch = async (input, options = {}) => {
  const path = new URL(input, location.href).pathname
  const body = typeof options.body === 'string' ? JSON.parse(options.body) : null
  window.loginTest.calls.push({ path, body })
  const data = path.endsWith('/auth/login') ? { detail: 'Test invalid credentials' } : { detail: 'Not authenticated' }
  return new Response(JSON.stringify(data), { status: 401, headers: { 'Content-Type': 'application/json' } })
}
createRoot(document.getElementById('root')).render(<BrowserRouter><AuthProvider><Routes><Route path="*" element={<LoginPage />} /></Routes></AuthProvider></BrowserRouter>)
