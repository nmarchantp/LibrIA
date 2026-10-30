import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import react from '@vitejs/plugin-react'

const server = await createServer({ configFile: false, plugins: [react(), {
  name: 'isolated-library',
  enforce: 'pre',
  resolveId(source) { if (/LibraryContext(?:\.jsx)?$/.test(source)) return '\0library-fixture' },
  load(id) { if (id === '\0library-fixture') return 'export function useLibrary() { return { getBook: () => null } }' },
}], optimizeDeps: { noDiscovery: true, entries: [] }, server: { middlewareMode: true }, appType: 'custom' })
try {
  const { default: BookExperience } = await server.ssrLoadModule('/src/components/BookExperience.jsx')
  const analysis = { id: 'stored', version: 1, content: {
    experience_summary: 'Interpretación anterior persistida.', event_kind: 'finish', evidence_ids: ['review:own'],
  } }
  const render = (status, extra = {}) => renderToStaticMarkup(React.createElement(BookExperience, {
    workId: 'own-book', refreshLabel: 'Actualizar estado', information: '',
    data: { status, analysis, needs_refresh: status !== 'completed', ...extra }, analysis,
  }))
  for (const state of ['update_pending', 'update_processing', 'failed']) {
    const html = render(state)
    assert.match(html, /Interpretación anterior persistida/)
    assert.match(html, /Actualización pendiente/)
  }
  assert.match(render('update_processing'), /Una nueva lechuza está en camino/)
  assert.match(render('failed'), /Programar reintento/)
  assert.doesNotMatch(render('failed', { retry_exhausted: true }), /Programar reintento/)
  assert.match(render('completed'), /Interpretación anterior persistida/)
  assert.doesNotMatch(render('completed'), /Actualización pendiente|ha regresado/)
  assert.match(render('requires_review'), /Escribir reseña/)
  const paused = render('update_pending', { generation_enabled: false, job: { status: 'pending' } })
  assert.match(paused, /generación está desactivada/)
  assert.match(paused, /Interpretación anterior persistida/)
  const retry = render('waiting_nightly_processing', { retry_scheduled: true })
  assert.match(retry, /generación anterior falló/)
  assert.doesNotMatch(retry, /medianoche/)
  console.log('Render del análisis persistido y sus actualizaciones: OK')
} finally { await server.close() }
