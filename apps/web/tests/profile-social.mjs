import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { profileDestination } from '../src/services/profileDestination.js'

const root = fileURLToPath(new URL('..', import.meta.url))
const profile = path.join(root, 'node_modules', '.cache', `social-browser-${process.pid}`)
const artifacts = path.resolve(root, '../../artifacts/profile-social')
await mkdir(profile, { recursive: true })
await mkdir(artifacts, { recursive: true })
const server = spawn(process.execPath, [path.join(root, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5197', '--strictPort'], { cwd: root, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
let serverLog = ''
server.stdout.on('data', chunk => { serverLog += chunk })
server.stderr.on('data', chunk => { serverLog += chunk })
const chrome = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe', ['--headless=new', '--disable-gpu', '--disable-background-networking', '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], { windowsHide: true, stdio: 'ignore' })
let ws
const delay = ms => new Promise(resolve => setTimeout(resolve, ms))
async function poll(check) {
  for (let i = 0; i < 150; i++) { try { const value = await check(); if (value) return value } catch { /* Wait for local services or rendering. */ } await delay(80) }
  throw Error('Timed out waiting for browser, server or UI')
}
try {
  const port = await poll(async () => (await readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0])
  await poll(async () => {
    if (server.exitCode !== null) throw Error(serverLog)
    return (await fetch('http://127.0.0.1:5197', { signal: AbortSignal.timeout(600) })).ok
  }).catch(error => { throw Error(`${error.message}\n${serverLog}`) })
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
    const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
    if (result.error || result.result?.exceptionDetails) throw Error(JSON.stringify(result))
    return result.result.result.value
  }
  const until = expression => poll(() => evaluate(`Boolean(${expression})`)).catch(async () => {
    throw Error(`Timed out: ${expression}\n${await evaluate('document.body.innerText')}\n${JSON.stringify(errors)}`)
  })
  const click = text => evaluate(`(() => {const button=[...document.querySelectorAll('button')].find(node=>node.textContent.trim()===${JSON.stringify(text)});if(!button)throw Error('Button missing');button.click()})()`)
  const close = async () => { await click('Listo'); await until(`!document.querySelector('dialog[open]')`) }
  await send('Runtime.enable')
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1050, deviceScaleFactor: 1, mobile: false })
  await send('Page.navigate', { url: 'http://127.0.0.1:5197/tests/fixtures/profile-social.html' })
  await until(`document.querySelector('.profile-community-counter strong')?.textContent==='7'`)
  // New lazy QR imports can trigger one Vite dependency optimization reload.
  await delay(700)
  await until(`document.querySelector('.profile-community-counter strong')?.textContent==='7'`)
  assert.deepEqual(await evaluate(`[...document.querySelectorAll('.profile-community-counter strong')].map(node=>node.textContent)`), ['7', '2', '3'])
  assert.equal(await evaluate(`(()=>{const joined=document.querySelector('.reader-profile-joined').getBoundingClientRect(),stats=document.querySelector('.profile-community-counters').getBoundingClientRect(),tabs=document.querySelector('.reader-profile-tabs').getBoundingClientRect();return joined.bottom<stats.top&&stats.bottom<tabs.top&&[...document.querySelectorAll('.profile-community-counter')].every(node=>node.querySelector('strong').getBoundingClientRect().bottom<=node.querySelector('span').getBoundingClientRect().top)})()`), true)
  let shot = await send('Page.captureScreenshot', { format: 'png' })
  await writeFile(path.join(artifacts, 'profile-desktop.png'), Buffer.from(shot.result.data, 'base64'))
  await evaluate(`document.querySelectorAll('.profile-community-counter')[1].click()`)
  await until(`document.querySelector('dialog[open] .profile-person-link')`)
  assert.match(await evaluate(`document.querySelector('dialog').textContent`), /Seguidores.*Camila Lectora/s)
  assert.equal(await evaluate(`document.querySelector('dialog .profile-person-link').getAttribute('href')`), '/profiles/person-1')
  await close()
  await evaluate(`document.querySelectorAll('.profile-community-counter')[2].click()`)
  await until(`document.querySelector('dialog[open] .profile-person-link')`)
  assert.match(await evaluate(`document.querySelector('dialog h2').textContent`), /Seguidos/)
  await close()
  await click('Editar privacidad')
  await until(`document.querySelector('dialog select')`)
  await evaluate(`(()=>{const node=document.querySelector('dialog select');node.value='private';node.dispatchEvent(new Event('change',{bubbles:true}))})()`)
  await until(`window.socialTest.saves.some(item=>item.profile_visibility==='private')`)
  await evaluate(`document.querySelector('dialog input[type=checkbox]').click()`)
  await until(`window.socialTest.saves.some(item=>item.public_sections?.length===1)`)
  await close()
  await click('Compartir perfil')
  await until(`document.querySelector('.profile-share-qr img')?.naturalWidth>0`)
  const url = await evaluate(`document.querySelector('#profile-share-url').value`)
  assert.equal(url, 'http://127.0.0.1:5197/profiles/profile-me?follow=1')
  assert.match(await evaluate(`document.querySelector('.profile-share-qr img').src`), /^data:image\/png;base64,/)
  assert.equal(await evaluate(`document.querySelector('.profile-share-name strong').textContent`), 'Valentina Lectora')
  for (const theme of ['lavanda', 'otono', 'invierno', 'rosa-antiguo', 'bosque', 'dark', 'dark-rosado', 'dark-blood', 'dark-dorado']) {
    const previous = await evaluate(`document.querySelector('.profile-share-qr img')?.src`)
    const current = await evaluate(`document.documentElement.dataset.theme`)
    await evaluate(`window.socialTest.selectTheme(${JSON.stringify(theme)})`)
    await until(`document.querySelector('.profile-share-qr img')?.naturalWidth>0${current === theme ? '' : `&&document.querySelector('.profile-share-qr img').src!==${JSON.stringify(previous)}`}`)
    assert.equal(await evaluate(`window.decodeSharedQr()`), url, `QR must decode to the exact user's profile in ${theme}`)
    assert.equal(await evaluate(`window.decodeSharedQr(undefined, 320)`), url, `Displayed QR must decode in ${theme}`)
    assert.equal(await evaluate(`document.querySelector('.profile-share-name strong').textContent`), 'Valentina Lectora')
  }
  for (const profileUrl of [
    'http://localhost:5173/profiles/14480da5-88ea-5802-b22a-e8c40e3f7e28?follow=1',
    'https://comunidad.libriaverse.example/profiles/14480da5-88ea-5802-b22a-e8c40e3f7e28?follow=1',
  ]) {
    for (const theme of ['lavanda', 'dark-dorado', 'dark-blood']) {
      for (const width of [320, 240]) {
        assert.equal(await evaluate(`window.checkProfileQr(${JSON.stringify(profileUrl)}, ${JSON.stringify(theme)}, ${width})`), profileUrl, `Larger book and round dots must decode at ${width}px in ${theme}`)
      }
    }
  }
  shot = await send('Page.captureScreenshot', { format: 'png' })
  await writeFile(path.join(artifacts, 'share-qr.png'), Buffer.from(shot.result.data, 'base64'))
  await close()
  await click('Descubrir personas')
  await until(`document.querySelectorAll('.profile-people-grid li').length===2`)
  await click('Seguir')
  await until(`window.socialTest.follows.length===1&&document.querySelectorAll('.profile-community-counter strong')[2].textContent==='4'`)
  assert.match(await evaluate(`document.querySelector('.profile-person-follow').textContent`), /Siguiendo/)
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  await until(`document.querySelector('dialog').getBoundingClientRect().width<=390`)
  assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth&&document.querySelector('dialog').getBoundingClientRect().right<=innerWidth`), true)
  shot = await send('Page.captureScreenshot', { format: 'png' })
  await writeFile(path.join(artifacts, 'discover-mobile.png'), Buffer.from(shot.result.data, 'base64'))
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape' })
  await until(`!document.querySelector('dialog[open]')`)
  assert.equal(errors.length, 0, JSON.stringify(errors))
  assert.equal(profileDestination(`next=${encodeURIComponent('/profiles/profile-me?follow=1')}`), '/profiles/profile-me?follow=1')
  assert.equal(profileDestination('next=https://evil.example'), '/')
  assert.equal(profileDestination('next=//evil.example'), '/')
  console.log('PASS: counters and placement, followers/seguidos dialogs, privacy persistence, QR generation, discovery follow/count update, mobile layout, Escape and safe login destination')
} finally {
  ws?.close()
  chrome.kill()
  server.kill()
}
