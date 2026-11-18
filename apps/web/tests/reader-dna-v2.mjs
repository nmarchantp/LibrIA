import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const profile = path.join(root, 'node_modules/.cache', `dna-v2-${process.pid}`)
const artifacts = path.resolve(root, '../../artifacts/reader-dna-v2')
await mkdir(profile, { recursive: true }); await mkdir(artifacts, { recursive: true })
const delay = ms => new Promise(resolve => setTimeout(resolve, ms))
async function until(check) {
  for (let i = 0; i < 150; i++) { try { if (await check()) return } catch { /* Wait for startup. */ } await delay(100) }
  throw Error('Timed out')
}
const server = spawn(process.execPath, [path.join(root, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5199', '--strictPort'], { cwd: root, windowsHide: true, stdio: 'ignore' })
const browser = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe', ['--headless=new', '--disable-gpu', '--disable-background-networking', '--no-first-run', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], { windowsHide: true, stdio: 'ignore' })
let ws
try {
  let port
  await until(async () => { port = (await readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; return port })
  await until(async () => (await fetch('http://127.0.0.1:5199', { signal: AbortSignal.timeout(1000) })).ok)
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT', signal: AbortSignal.timeout(5000) })).json()
  ws = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject })
  let sequence = 0
  const pending = new Map(), errors = []
  ws.onmessage = event => { const message = JSON.parse(event.data); if (message.method === 'Runtime.exceptionThrown') errors.push(message.params); if (pending.has(message.id)) { pending.get(message.id)(message); pending.delete(message.id) } }
  const send = (method, params = {}) => new Promise(resolve => { pending.set(++sequence, resolve); ws.send(JSON.stringify({ id: sequence, method, params })) })
  const evaluate = async expression => {
    const response = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (response.error || response.result.exceptionDetails) throw Error(JSON.stringify(response))
    return response.result.result.value
  }
  await send('Runtime.enable')
  await send('Page.navigate', { url: 'http://127.0.0.1:5199/tests/fixtures/reader-dna-v2.html' })
  await until(() => evaluate(`Boolean(document.querySelector('.dna-essence h3'))`))
  // Let the first Vite dependency optimization settle before interacting.
  await delay(800)
  assert.equal(await evaluate(`window.dnaTest.historyReads`), 0, 'History is not fetched on profile display')
  assert.equal(await evaluate(`document.querySelectorAll('.dna-bento > .dna-section').length`), 7)
  await evaluate(`document.querySelector('.dna-evolution > button').click()`)
  await until(() => evaluate(`document.querySelectorAll('.dna-timeline > li').length === 2`))
  assert.equal(await evaluate(`document.querySelectorAll('.dna-version-comparison select option').length`), 2, 'Current version cannot be selected as a prior version')
  await evaluate(`(()=>{const select=document.querySelector('select');select.value='old-analysis';select.dispatchEvent(new Event('change',{bubbles:true}))})()`)
  await until(() => evaluate(`document.querySelectorAll('.dna-comparison-dimension').length === 7`))
  for (const theme of ['lavanda', 'dark']) {
    await evaluate(`window.dnaTest.selectTheme(${JSON.stringify(theme)})`)
    for (const width of [1440, 390]) {
      await send('Emulation.setDeviceMetricsOverride', { width, height: 1000, deviceScaleFactor: 1, mobile: width < 500 })
      await delay(100)
      assert.equal(await evaluate(`document.documentElement.scrollWidth <= innerWidth + 1`), true, `${theme}/${width}: no overflow`)
      assert.equal(await evaluate(`getComputedStyle(document.querySelector('.dna-comparison-columns')).gridTemplateColumns.split(' ').length`), width < 500 ? 1 : 2)
      const screenshot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
      await writeFile(path.join(artifacts, `${theme}-${width}.png`), Buffer.from(screenshot.result.data, 'base64'))
    }
  }
  for (const [mode, phrase] of [['insufficient', 'Todavía faltan reflexiones'], ['legacy', 'Este análisis es de una versión anterior']]) {
    await evaluate(`window.dnaTest.setMode(${JSON.stringify(mode)})`)
    await until(() => evaluate(`document.querySelector('.dna-essence').textContent.includes(${JSON.stringify(phrase)})`))
  }
  assert.deepEqual(errors, [])
  console.log('PASS: essence, 7 dimensions, history on demand, version comparison, legacy/insufficient states, light/dark and desktop/mobile')
} finally { ws?.close(); browser.kill(); server.kill() }
