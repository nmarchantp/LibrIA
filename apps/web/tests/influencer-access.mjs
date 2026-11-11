import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const profile = path.join(root, 'node_modules/.cache', `influencer-access-${process.pid}`)
await mkdir(profile, { recursive: true })
const server = spawn(process.execPath, [path.join(root, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5198', '--strictPort'], { cwd: root, windowsHide: true, stdio: 'ignore' })
const chrome = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe', ['--headless=new', '--disable-gpu', '--disable-background-networking', '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], { windowsHide: true, stdio: 'ignore' })
const delay = ms => new Promise(resolve => setTimeout(resolve, ms))
async function poll(check) {
  for (let i = 0; i < 150; i++) {
    try { const result = await check(); if (result) return result } catch { /* Wait for local browser and React. */ }
    await delay(80)
  }
  throw Error('Timed out waiting for isolated browser UI')
}
let ws
try {
  const port = await poll(async () => (await readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0])
  await poll(async () => (await fetch('http://127.0.0.1:5198')).ok)
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json()
  ws = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject })
  let sequence = 0
  const pending = new Map(), errors = []
  ws.onmessage = event => {
    const message = JSON.parse(event.data)
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params)
    if (pending.has(message.id)) { pending.get(message.id)(message); pending.delete(message.id) }
  }
  const send = (method, params = {}) => new Promise(resolve => { pending.set(++sequence, resolve); ws.send(JSON.stringify({ id: sequence, method, params })) })
  async function evaluate(expression) {
    const response = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
    if (response.error || response.result?.exceptionDetails) throw Error(JSON.stringify(response))
    return response.result.result.value
  }
  const until = expression => poll(() => evaluate(`Boolean(${expression})`)).catch(async error => { throw Error(`${error.message}\n${expression}\n${await evaluate('document.body.innerText')}`) })
  const click = text => evaluate(`(() => { const button = [...document.querySelectorAll('button')].find(item => item.textContent.trim() === ${JSON.stringify(text)}); if (!button || button.disabled) throw Error('Button unavailable: ' + ${JSON.stringify(text)}); button.click() })()`)
  const fill = (selector, value) => evaluate(`(() => { const input = document.querySelector(${JSON.stringify(selector)}); Object.getOwnPropertyDescriptor(input.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, 'value').set.call(input, ${JSON.stringify(value)}); input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true })) })()`)
  async function apply() {
    await until(`document.querySelector('.role-panel form')`)
    await fill('.role-panel form textarea', 'Comparto reseñas literarias para lectores de fantasía.')
    await fill('.role-panel form input', 'Fantasía, misterio')
    await fill('.role-panel form label:nth-of-type(3) textarea', 'Deseo compartir recomendaciones con mi comunidad.')
    await fill('.role-panel form label:nth-of-type(4) textarea', 'https://youtube.com/@reader')
    await click('Enviar solicitud de Influencer')
    await until(`document.body.innerText.includes('Pendiente')`)
    assert.equal(await evaluate(`document.querySelector('.role-panel form') === null`), true)
  }
  async function decide(action, observation) {
    await click('admin')
    await until(`document.body.innerText.includes('Solicitudes pendientes (1)')`)
    await click('Solicitudes pendientes (1)')
    await until(`document.querySelector('.admin-request textarea')`)
    assert.equal(await evaluate(`document.querySelector('.admin-request-actions button').disabled`), true)
    assert.equal(await evaluate(`document.querySelector('.admin-request a').rel`), 'noopener noreferrer')
    await fill('.admin-request textarea', observation)
    await click(action)
    await until(`!document.querySelector('.admin-request')`)
  }
  await send('Runtime.enable')
  await send('Page.navigate', { url: 'http://127.0.0.1:5198/tests/fixtures/influencer-access.html' })
  await apply()
  await decide('Rechazar', 'Falta evidencia de publicaciones literarias recientes.')
  await click('reader')
  await until(`document.body.innerText.includes('Rechazada') && document.body.innerText.includes('Administrador de prueba')`)
  await apply()
  await decide('Aprobar', 'Actividad y enlaces literarios revisados correctamente.')
  await click('Perfiles')
  await until(`document.querySelector('.admin-profile-row')`)
  await evaluate(`document.querySelector('.admin-profile-row').click()`)
  await until(`document.querySelector('[aria-label="Permisos de Influencer"] textarea')`)
  const panel = '[aria-label="Permisos de Influencer"]'
  await fill(`${panel} textarea`, 'Suspensión temporal durante la revisión de permisos.')
  await fill(`${panel} input`, '2098-12-01T18:30')
  await click('Suspender permisos')
  await until(`window.influencerTest.actions.length === 1 && document.body.innerText.includes('Reactivar permisos')`)
  await fill(`${panel} textarea`, 'Revisión terminada, permisos de publicación restituidos.')
  await click('Reactivar permisos')
  await until(`window.influencerTest.actions.length === 2 && !document.body.innerText.includes('Reactivar permisos')`)
  await fill(`${panel} textarea`, 'Revocación del tipo Influencer por revisión administrativa.')
  await click('Revocar perfil Influencer')
  await until(`window.influencerTest.reader.role === 'lector' && !document.body.innerText.includes('Revocar perfil Influencer')`)
  assert.equal(await evaluate(`window.influencerTest.actions.every(item => item.reason.length >= 10)`), true)
  await click('reader')
  await until(`document.querySelector('.role-panel form') && document.body.innerText.includes('Aprobada')`)
  assert.equal(errors.length, 0, JSON.stringify(errors))
  console.log('PASS RF-INF-001..004: real account component, structured application, rejection/reapplication, approval with reviewer/date/observation, suspension, resume, revocation and audit UI (mock API)')
} finally {
  ws?.close()
  chrome.kill()
  server.kill()
}
