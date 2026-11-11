import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const profile = path.join(root, 'node_modules/.cache', `role-notifications-${process.pid}`)
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
  await send('Runtime.enable')
  await send('Page.navigate', { url: 'http://127.0.0.1:5198/tests/fixtures/role-notifications.html' })
  await until(`document.querySelector('.notification-shortcut-count')?.textContent === '1' && document.body.innerText.includes('Revisar solicitudes')`)
  assert.equal(await evaluate(`document.querySelector('.notification a').getAttribute('href')`), '/admin/profiles?tab=requests')
  await click('Marcar como le\u00edda')
  await until(`!document.querySelector('.notification-shortcut-count')`)
  await click('lector')
  await until(`document.querySelector('.notification-shortcut-count')?.textContent === '1' && document.body.innerText.includes('Falta evidencia')`)
  assert.equal(await evaluate(`document.querySelector('.notification a').getAttribute('href')`), '/settings')
  await click('Marcar como le\u00edda')
  await until(`!document.querySelector('.notification-shortcut-count')`)
  assert.equal(errors.length, 0, JSON.stringify(errors))
  console.log('PASS: admin application alert, reader rejection reason, independent unread badge, private links and mark-as-read refresh')
} finally {
  ws?.close()
  chrome.kill()
  server.kill()
}
