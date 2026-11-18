import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const delay = ms => new Promise(resolve => setTimeout(resolve, ms))
async function until(check) {
  for (let i = 0; i < 160; i++) {
    try { const result = await check(); if (result) return result } catch { /* Wait for startup. */ }
    await delay(100)
  }
  throw Error('Timed out')
}
const server = spawn(process.execPath, [path.join(root, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5198', '--strictPort'], { cwd: root, windowsHide: true, stdio: 'ignore' })
try {
  await until(async () => (await fetch('http://127.0.0.1:5198', { signal: AbortSignal.timeout(1000) })).ok)
  for (const [name, binary] of [['Chrome', 'C:/Program Files/Google/Chrome/Application/chrome.exe'], ['Edge', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe']]) {
    const profile = path.join(root, 'node_modules/.cache', `carousel-${name}-${process.pid}`)
    await mkdir(profile, { recursive: true })
    const browser = spawn(binary, ['--headless=new', '--disable-gpu', '--disable-background-networking', '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], { windowsHide: true, stdio: 'ignore' })
    let ws
    try {
      const port = await until(async () => (await readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0])
      const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT', signal: AbortSignal.timeout(5000) })).json()
      ws = new WebSocket(target.webSocketDebuggerUrl)
      await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject })
      let sequence = 0
      const pending = new Map()
      ws.onmessage = event => { const message = JSON.parse(event.data); if (pending.has(message.id)) { pending.get(message.id)(message); pending.delete(message.id) } }
      const send = (method, params = {}) => new Promise(resolve => { pending.set(++sequence, resolve); ws.send(JSON.stringify({ id: sequence, method, params })) })
      const evaluate = async expression => {
        const response = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
        if (response.error || response.result.exceptionDetails) throw Error(JSON.stringify(response))
        return response.result.result.value
      }
      await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
      await send('Page.navigate', { url: 'http://127.0.0.1:5198/tests/fixtures/literary-carousel.html' })
      await until(() => evaluate(`document.querySelector('.registration-carousel-controls span')?.textContent === '1 de 5'`))
      assert.equal(await evaluate(`getComputedStyle(document.querySelector('.registration-carousel-cover')).transitionDuration`), '3.2s, 3.2s', `${name}: explicit setting overrides reduced motion`)
      // Actual automatic timer, with reduced motion emulated in both browsers.
      await until(() => evaluate(`document.querySelector('.registration-carousel-controls span').textContent === '2 de 5'`))
      const before = await evaluate(`getComputedStyle(document.querySelector('.registration-carousel-cover.is-current')).transform`)
      await delay(500)
      const after = await evaluate(`getComputedStyle(document.querySelector('.registration-carousel-cover.is-current')).transform`)
      assert.notEqual(before, after, `${name}: intermediate frames move instead of jumping`)
      assert.notEqual(after, 'matrix(1, 0, 0, 1, 0, 0)', `${name}: transition has not snapped to its endpoint`)
      await evaluate(`document.querySelector('#motion').click()`)
      await delay(100)
      const paused = await evaluate(`document.querySelector('.registration-carousel-controls span').textContent`)
      await delay(7300)
      assert.equal(await evaluate(`document.querySelector('.registration-carousel-controls span').textContent`), paused, `${name}: disabled setting stops automatic advance`)
      await evaluate(`document.querySelector('#motion').click()`)
      await until(() => evaluate(`document.querySelector('.registration-carousel-controls span').textContent !== ${JSON.stringify(paused)}`))
      console.log(`PASS ${name}: automatic advance, smooth intermediate frames despite reduced motion, pause and resume from shared setting`)
    } finally { ws?.close(); browser.kill() }
  }
} finally { server.kill() }
