import { createRoot } from 'react-dom/client'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '/src/context/AuthContext'
import { authService } from '/src/services/authService'
import AdminGate from '/src/components/AdminGate'
import SessionGate from '/src/components/SessionGate'
import AdminCatalogPage from '/src/components/CatalogGroupingPanel'
import { applyTheme } from '/src/theme/themes'
import '/src/styles.css'
import '/src/theme/themes.css'

const params = new URLSearchParams(location.search)
applyTheme(params.get('theme') || 'dark')
localStorage.setItem('libria_token','isolated-ui-test')
authService.me = async () => ({ id:'fixture',role:params.get('role') || 'lector' })
const side = id => ({ canonical_id:id,works:[{ title:`Obra ${id}` }],authors:[],editions:[],references:[] })
window.catalogTest = { calls:[],fail:false }
window.fetch = async url => {
  const path = new URL(url,location.origin).pathname
  window.catalogTest.calls.push(path)
  let payload = {}
  let status = 200
  if (path.endsWith('/roles/access')) payload={ admin:params.get('admin')!=='false',catalog_preview:params.get('preview')!=='false' }
  else if (path.endsWith('/works')) payload=[{id:'a',title:'Obra A'},{id:'b',title:'Obra B'}]
  else if (window.catalogTest.fail) { status=503;payload={detail:'Error de prueba recuperable'} }
  else payload={ source:side('a'),target:side('b'),evidence:{automatic_merge_allowed:false},conflicts:[],impact:{reading_attempts:2},decisions:['Revisión administrativa'],
    ...(path.endsWith('/merge-previews') ? { preview_id:'preview-fixture',expires_at:'2026-12-01',fingerprint:'sha256-fixture' } : {}) }
  return new Response(JSON.stringify(payload),{status,headers:{'Content-Type':'application/json'}})
}
createRoot(document.getElementById('root')).render(<AuthProvider><MemoryRouter initialEntries={['/admin/catalog']}><Routes>
  <Route element={<SessionGate />}><Route element={<AdminGate />}><Route path="/admin/catalog" element={<AdminCatalogPage />} /></Route></Route>
  <Route path="/" element={<p>Acceso denegado</p>} />
</Routes></MemoryRouter></AuthProvider>)
