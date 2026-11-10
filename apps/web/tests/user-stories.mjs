import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const profile = path.join(root, 'node_modules/.cache', `stories-browser-${process.pid}`)
const artifacts = path.resolve(root, '../../artifacts/user-stories')
await mkdir(profile, { recursive: true }); await mkdir(artifacts, { recursive: true })
const server = spawn(process.execPath, [path.join(root, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5198', '--strictPort'], { cwd: root, windowsHide: true, stdio: 'ignore' })
const chrome = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe', ['--headless=new', '--disable-gpu', '--disable-background-networking', '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], { windowsHide: true, stdio: 'ignore' })
let ws
const delay = ms => new Promise(resolve => setTimeout(resolve, ms))
async function poll(check) {
  for (let i = 0; i < 120; i++) { try { const result = await check(); if (result) return result } catch { /* Wait for local startup. */ } await delay(100) }
  throw Error('Timed out waiting for local browser or UI')
}
try {
  const port = await poll(async () => (await readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0])
  await poll(async () => (await fetch('http://127.0.0.1:5198', { signal: AbortSignal.timeout(500) })).ok)
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT', signal: AbortSignal.timeout(5000) })).json()
  ws = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; setTimeout(() => reject(Error('CDP connection timeout')), 10000).unref() })
  let sequence = 0
  const pending = new Map(), errors = []
  ws.onmessage = event => {
    const message = JSON.parse(event.data)
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params)
    if (pending.has(message.id)) { pending.get(message.id)(message); pending.delete(message.id) }
  }
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence
    const timeout = setTimeout(() => { pending.delete(id); reject(Error(`CDP timeout: ${method}`)) }, 10000)
    pending.set(id, result => { clearTimeout(timeout); resolve(result) }); ws.send(JSON.stringify({ id, method, params }))
  })
  async function evaluate(expression) {
    const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
    if (result.error || result.result?.exceptionDetails) throw Error(JSON.stringify(result))
    return result.result.result.value
  }
  const until = expression => poll(() => evaluate(`Boolean(${expression})`)).catch(async () => { throw Error(`Timed out: ${expression}\n${await evaluate('document.body.innerText')}\n${JSON.stringify(errors)}`) })
  const click = label => evaluate(`(()=>{const button=document.querySelector('button[aria-label="${label}"]');button.focus();button.click()})()`)
  const key = async name => { const windowsVirtualKeyCode = { Escape: 27, ArrowLeft: 37, ArrowRight: 39 }[name]; await send('Input.dispatchKeyEvent', { type: 'keyDown', key: name, code: name, windowsVirtualKeyCode }); await send('Input.dispatchKeyEvent', { type: 'keyUp', key: name, code: name, windowsVirtualKeyCode }) }
  await send('Runtime.enable')
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  await send('Page.navigate', { url: 'http://127.0.0.1:5198/tests/fixtures/user-stories.html' })
  await until(`document.querySelector('.profile-story-avatar.has-stories') && document.querySelectorAll('.user-story-person').length===2`)
  await until(`document.querySelector('.user-story-own .story-avatar-photo img')?.naturalWidth>0`)
  assert.equal(await evaluate(`document.querySelectorAll('.user-story-own').length`), 1)
  assert.equal(await evaluate(`document.querySelectorAll('.user-stories .story-star-ring.is-unseen').length`), 2)
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.user-story-own .story-ring-orbit')).animationName`), 'story-light-orbit')
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.user-story-own .story-ring-orbit')).animationName`), 'story-light-orbit')
  const beforeOrbit = await evaluate(`getComputedStyle(document.querySelector('.user-story-own .story-ring-orbit')).transform`)
  await delay(250)
  assert.notEqual(await evaluate(`getComputedStyle(document.querySelector('.user-story-own .story-ring-orbit')).transform`), beforeOrbit)
  assert.equal(await evaluate(`(()=>{const avatar=document.querySelector('.user-story-avatar').getBoundingClientRect(),photo=document.querySelector('.user-story-avatar .story-avatar-photo').getBoundingClientRect();return Math.abs(avatar.width-avatar.height)<.1&&Math.abs((avatar.left+avatar.right)-(photo.left+photo.right))<.1&&Math.abs((avatar.top+avatar.bottom)-(photo.top+photo.bottom))<.1})()`), true)
  await click('Ver historias de Valentina Lectora')
  await until(`document.querySelector('dialog[open] .user-story-image')?.naturalWidth>0`)
  assert.equal(await evaluate(`document.body.style.overflow`), 'hidden')
  assert.equal(await evaluate(`document.querySelector('dialog').matches(':modal')`), true)
  assert.equal(await evaluate(`(()=>{const r=document.querySelector('.user-story-stage').getBoundingClientRect();return Math.abs(r.width/r.height-9/16)<.002})()`), true)
  await click('Pausar historias')
  await key('ArrowRight')
  await until(`document.querySelector('.user-story-footer').textContent.startsWith('2 /')`)
  await click('Siguiente historia')
  await until(`document.querySelector('.user-story-heading strong').textContent==='Camila entre libros'`)
  await until(`document.querySelector('.user-stories-row > .user-story-person .story-star-ring.is-seen')`)
  assert.equal(await evaluate(`Boolean(document.querySelector('button[aria-label="Eliminar historia"]'))`), false)
  await key('ArrowLeft')
  await until(`document.querySelector('.user-story-heading strong').textContent==='Valentina Lectora'`)
  await click('Eliminar historia')
  await evaluate(`document.querySelector('.user-story-confirm button').click()`)
  await until(`!document.querySelector('.user-story-confirm') && document.querySelector('.user-story-footer').textContent.includes('/ 2')`)
  await key('Escape')
  await until(`!document.querySelector('dialog[open]')`)
  assert.equal(await evaluate(`document.activeElement.getAttribute('aria-label')`), 'Ver historias de Valentina Lectora')
  await until(`document.querySelector('.user-story-own .story-star-ring.is-seen')`)
  assert.equal(await evaluate(`[...document.querySelectorAll('.user-story-own .story-star-ring *')].every(node=>getComputedStyle(node).animationName==='none')`), true)
  await click('Agregar historia desde contactos')
  await until(`document.querySelector('.user-story-composer')`)
  await evaluate(`(async()=>{const canvas=document.createElement('canvas');canvas.width=300;canvas.height=200;const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));const transfer=new DataTransfer();transfer.items.add(new File([blob],'test.png',{type:'image/png'}));const input=document.querySelector('input[type=file]');input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}))})()`)
  await until(`document.querySelector('.user-story-preview')?.naturalWidth===1080 && !document.querySelector('.user-story-publish').disabled`)
  assert.equal(await evaluate(`document.querySelector('.user-story-preview').naturalHeight`), 1920)
  await evaluate(`document.querySelector('.user-story-publish').click()`)
  await until(`window.storyTest.posts===1 && !document.querySelector('dialog[open]')`)
  await until(`document.querySelector('.user-story-own .story-star-ring.is-unseen')`)
  let ringShot = await send('Page.captureScreenshot', { format: 'png' })
  await writeFile(path.join(artifacts, 'story-rings-desktop.png'), Buffer.from(ringShot.result.data, 'base64'))
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  ringShot = await send('Page.captureScreenshot', { format: 'png' })
  await writeFile(path.join(artifacts, 'story-rings-mobile.png'), Buffer.from(ringShot.result.data, 'base64'))
  await click('Ver historias de Camila entre libros')
  await until(`document.querySelector('dialog[open] .user-story-image')?.naturalWidth>0`)
  await click('Pausar historias')
  assert.equal(await evaluate(`(()=>{const r=document.querySelector('dialog').getBoundingClientRect();return r.width<=innerWidth&&r.height<=innerHeight&&document.documentElement.scrollWidth<=innerWidth})()`), true)
  const shot = await send('Page.captureScreenshot', { format: 'png' })
  await writeFile(path.join(artifacts, 'stories-mobile.png'), Buffer.from(shot.result.data, 'base64'))
  await evaluate(`(()=>{const node=document.querySelector('.user-story-stage');node.dispatchEvent(new TouchEvent('touchstart',{bubbles:true,touches:[new Touch({identifier:1,target:node,clientX:50,clientY:300})]}));node.dispatchEvent(new TouchEvent('touchend',{bubbles:true,changedTouches:[new Touch({identifier:1,target:node,clientX:180,clientY:300})]}))})()`)
  await until(`document.querySelector('.user-story-heading strong').textContent==='Valentina Lectora'`)
  await key('Escape')
  await until(`!document.querySelector('dialog[open]')`)
  await evaluate(`window.storyTest.fail=true;window.dispatchEvent(new Event('libria:stories-changed'))`)
  await until(`document.querySelector('.user-stories [role=alert]')`)
  await evaluate(`window.storyTest.fail=false;document.querySelector('.user-stories [role=alert] button').click()`)
  await until(`document.querySelectorAll('.user-story-person').length===2`)
  await click('Ver mis historias')
  await until(`document.querySelector('.user-story-footer')?.textContent.startsWith('2 /')`)
  await key('Escape')
  await until(`!document.querySelector('dialog[open]')`)
  assert.equal(errors.length, 0, JSON.stringify(errors))
  console.log('PASS: profile ring, 9:16 modal, keyboard/user navigation, pause, owner deletion, Escape/focus, publication, mobile swipe/layout, error/retry')
} finally { ws?.close(); chrome.kill(); server.kill() }
