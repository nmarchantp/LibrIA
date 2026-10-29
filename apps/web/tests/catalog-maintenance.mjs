// Browser integration with mocked HTTP: no writes to the development catalog.
import assert from 'node:assert/strict'
import fs from 'node:fs'
const cdp = process.env.CDP_URL || 'http://127.0.0.1:9241'
const app = process.env.VITE_URL || 'http://127.0.0.1:5173'
const target = await (await fetch(`${cdp}/json/new?about:blank`, { method: 'PUT' })).json()
const socket = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
let sequence = 0
const pending = new Map()
socket.onmessage = event => { const response = JSON.parse(event.data); if (pending.has(response.id)) { pending.get(response.id)(response); pending.delete(response.id) } }
const send = (method, params = {}) => new Promise(resolve => { pending.set(++sequence, resolve); socket.send(JSON.stringify({ id: sequence, method, params })) })
async function evaluate(expression) {
  const response = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (response.result?.exceptionDetails) throw Error(JSON.stringify(response.result.exceptionDetails))
  return response.result.result.value
}
async function until(expression) { for (let index = 0; index < 150; index++) { if (await evaluate(expression)) return; await new Promise(resolve => setTimeout(resolve, 50)) } throw Error('Timed out: ' + expression) }
async function click(text) { await evaluate(`[...document.querySelectorAll('button')].find(button => button.textContent.trim() === ${JSON.stringify(text)}).click()`) }
async function field(label, value) {
  await evaluate(`(() => { const input = [...document.querySelectorAll('dialog label')].find(label => label.firstChild.textContent === ${JSON.stringify(label)}).querySelector('input,textarea'); Object.getOwnPropertyDescriptor(input.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, 'value').set.call(input, ${JSON.stringify(value)}); input.dispatchEvent(new Event('input', { bubbles: true })) })()`)
}
try {
  await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 960, deviceScaleFactor: 1, mobile: false })
  await send('Page.navigate', { url: app + '/tests/fixtures/catalog-maintenance.html' })
  await until("document.querySelectorAll('.catalog-inventory-table tbody tr').length === 2")
  assert.equal(await evaluate("document.querySelector('h1').textContent"), 'Mantenedor de libros')
  fs.mkdirSync('../../.tmp', { recursive: true })
  fs.writeFileSync('../../.tmp/catalog-maintainer-desktop.png', Buffer.from((await send('Page.captureScreenshot', { format: 'png' })).result.data, 'base64'))
  await click('Gestionar')
  await until("document.querySelector('dialog[open] input') !== null")
  await field('Título de la obra', 'Una corte de rosas y espinas · revisada')
  await field('Motivo del cambio', 'Corrección de título desde el mantenedor')
  await click('Guardar ficha')
  await until("document.querySelector('dialog [role=status]')?.textContent.includes('guardados')")
  assert.equal(await evaluate("window.maintenanceTest.books.a.title"), 'Una corte de rosas y espinas · revisada')
  await click('Ediciones (1)')
  await click('Editar edición')
  await field('Número de páginas', '345')
  await field('Motivo del cambio', 'Corregir las páginas de esta edición')
  await click('Guardar edición')
  await until("document.querySelector('.catalog-managed-editions')?.textContent.includes('345 páginas')")
  await evaluate("document.querySelector('[aria-label=\"Cerrar editor\"]').click()")
  await until("document.querySelector('dialog') === null")
  await evaluate("document.querySelectorAll('.catalog-inventory-table input[type=checkbox]').forEach(input => input.click())")
  await click('Revisar agrupación')
  await until("document.querySelector('.catalog-selection.is-selected') !== null")
  await click('Simular fusión')
  await until("document.body.textContent.includes('Resolución explícita de conflictos')")
  await evaluate("document.querySelector('fieldset input[type=checkbox]').click()")
  await evaluate("(() => { for (const [element, value] of [[document.querySelector('fieldset textarea'), 'Agrupar ediciones de la misma novela'], [document.querySelector('fieldset input:not([type=checkbox])'), 'FUSIONAR']]) { Object.getOwnPropertyDescriptor(element.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, 'value').set.call(element, value); element.dispatchEvent(new Event('input', { bubbles: true })) } })()")
  await click('Confirmar fusión administrativa')
  await until("document.body.textContent.includes('operation-fixture')")
  await click('Libros y ediciones')
  await until("document.querySelectorAll('.catalog-inventory-table tbody tr').length === 1")
  assert.equal(await evaluate("Object.values(window.maintenanceTest.books)[0].editions.length"), 2)
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'), true, 'Mobile catalog overflows')
  fs.writeFileSync('../../.tmp/catalog-maintainer-mobile.png', Buffer.from((await send('Page.captureScreenshot', { format: 'png' })).result.data, 'base64'))
  await click('Gestionar')
  await until("document.querySelector('dialog[open] input') !== null")
  assert.equal(await evaluate("document.querySelector('dialog').scrollWidth <= document.querySelector('dialog').clientWidth"), true, 'Mobile editor overflows')
  fs.writeFileSync('../../.tmp/catalog-maintainer-editor-mobile.png', Buffer.from((await send('Page.captureScreenshot', { format: 'png' })).result.data, 'base64'))
  await evaluate("document.querySelector('[aria-label=\"Cerrar editor\"]').click()")
  await until("document.querySelector('dialog') === null")
  await click('Nuevo libro')
  await until("document.querySelector('dialog[open] input') !== null")
  await field('Título de la obra', 'Libro manual de prueba')
  await field('Autores', 'Autora del catálogo')
  await field('Motivo del cambio', 'Registrar una obra desde el mantenedor')
  await click('Crear libro')
  await until("document.querySelector('dialog [role=status]')?.textContent.includes('guardados')")
  await click('Ediciones (0)')
  await click('Añadir edición')
  await field('ISBN', '9788478884452')
  await field('Número de páginas', '121')
  await field('Motivo del cambio', 'Añadir una edición verificada')
  await click('Añadir edición')
  await until("document.querySelector('.catalog-managed-editions')?.textContent.includes('121 páginas')")
  assert.equal(await evaluate('window.maintenanceTest.books.manual.editions.length'), 1)
  console.log('PASS: inventory, work and edition creation/correction, grouping with confirmation, result refresh, desktop and mobile layouts; HTTP mocked')
} finally { await send('Page.close'); socket.close() }
