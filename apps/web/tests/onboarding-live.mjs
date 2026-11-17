// Opt-in only: route API requests to the disposable local FastAPI instance.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
if (process.env.LIBRIA_LIVE_ONBOARDING_TEST !== '1') {
  console.log('SKIP: requires LIBRIA_LIVE_ONBOARDING_TEST=1 and isolated API on port 8012')
  process.exit(0)
}
const cdp = process.env.CDP_URL || 'http://127.0.0.1:9224'
const version = await (await fetch(`${cdp}/json/version`)).json()
function connect(url) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(url)
    socket.onerror = reject
    socket.onopen = () => {
      let sequence = 0
      const pending = new Map()
      socket.onmessage = event => { const value = JSON.parse(event.data); if (pending.has(value.id)) { pending.get(value.id)(value); pending.delete(value.id) } }
      resolve({ socket, call: (method, params = {}) => new Promise(resolve => { pending.set(++sequence, resolve); socket.send(JSON.stringify({ id: sequence, method, params })) }) })
    }
  })
}
const browser = await connect(version.webSocketDebuggerUrl)
const context = (await browser.call('Target.createBrowserContext')).result.browserContextId
const targetId = (await browser.call('Target.createTarget', { url: 'about:blank', browserContextId: context })).result.targetId
const target = (await (await fetch(`${cdp}/json/list`)).json()).find(item => item.id === targetId)
const page = await connect(target.webSocketDebuggerUrl)
async function evaluate(expression) {
  const value = await page.call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (value.result?.exceptionDetails) throw new Error(JSON.stringify(value.result.exceptionDetails))
  return value.result.result.value
}
async function until(expression) {
  for (let i = 0; i < 200; i++) { if (await evaluate(`Boolean(${expression})`)) return; await new Promise(resolve => setTimeout(resolve, 50)) }
  throw new Error('Timed out: ' + expression + '\n' + await evaluate('document.body.innerText'))
}
async function fill(name, text) {
  await evaluate(`(()=>{const e=document.querySelector('[name=${name}]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,${JSON.stringify(text)});e.dispatchEvent(new Event('input',{bubbles:true}))})()`)
}
const submit = () => evaluate(`document.querySelector('.register-card').requestSubmit()`)
async function screenshot(name) {
  await mkdir(new URL('../../../artifacts/onboarding-wizard/', import.meta.url), { recursive: true })
  const shot = await page.call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  await writeFile(new URL(`../../../artifacts/onboarding-wizard/${name}.png`, import.meta.url), Buffer.from(shot.result.data, 'base64'))
}
try {
  await page.call('Page.enable')
  const injection = await page.call('Page.addScriptToEvaluateOnNewDocument', { source: `{
    const original=window.fetch.bind(window);window.fetch=(input,options)=>{
      const url=new URL(typeof input==='string'?input:input.url,location.href);
      if(url.pathname.startsWith('/api/'))return original('http://127.0.0.1:8012'+url.pathname+url.search,options);
      return original(input,options);
    }
  }` })
  assert.equal(injection.error, undefined)
  await page.call('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  await page.call('Page.navigate', { url: 'http://127.0.0.1:5173/register' })
  await until(`document.querySelector('[name=password]')`)
  assert.equal(await evaluate(`String(window.fetch).includes('8012')`), true, 'Every API request must target the isolated server')
  const email = `wizard-${Date.now()}@example.com`
  await fill('name', 'Prueba integral'); await fill('email', email)
  await fill('password', 'IsolatedTest123!'); await fill('password_confirmation', 'IsolatedTest123!')
  await submit()
  await until(`document.querySelector('.registration-panel[aria-hidden=false] .registration-choices button') && !document.querySelector('.registration-actions .primary').disabled`)
  assert.equal(await evaluate(`location.pathname`), '/register')
  const headers = `{'Authorization':'Bearer '+localStorage.getItem('libria_token')}`
  assert.equal(await evaluate(`fetch('/api/readings/me',{headers:${headers}}).then(r=>r.status)`), 403)
  await evaluate(`document.querySelector('.registration-panel[aria-hidden=false] .registration-choices button').click()`)
  await submit()
  await until(`document.querySelector('#registration-heading')?.textContent.includes('atrapa') && !document.querySelector('.registration-actions .primary').disabled`)
  await page.call('Page.reload')
  await until(`document.querySelector('#registration-heading')?.textContent.includes('atrapa') && !document.querySelector('.registration-actions .primary').disabled`)
  for (const part of ['atrapa', 'sentir', 'describirías']) {
    await until(`document.querySelector('#registration-heading')?.textContent.includes(${JSON.stringify(part)}) && !document.querySelector('.registration-actions .primary').disabled`)
    await evaluate(`document.querySelector('.registration-panel[aria-hidden=false] .registration-choices button').click()`)
    await submit()
  }
  await until(`document.querySelector('#registration-heading')?.textContent.includes('huella') && !document.querySelector('.registration-actions .primary').disabled`)
  await submit()
  await until(`document.querySelector('#registration-heading')?.textContent.includes('estilo') && !document.querySelector('.registration-actions .primary').disabled`)
  await evaluate(`document.querySelector('.registration-theme-preview.lavanda').click()`)
  await screenshot('live-theme-390')
  await submit()
  await until(`document.querySelector('#registration-heading')?.textContent.includes('comienza') && !document.querySelector('.registration-actions .primary').disabled`)
  await submit()
  await until(`document.querySelector('.initial-literary-dna') && document.querySelector('.register-card').getAttribute('aria-busy')==='false'`)
  const me = await evaluate(`fetch('/api/auth/me',{headers:${headers}}).then(r=>r.json())`)
  assert.equal(me.onboarding_required, false); assert.equal(me.visual_theme, 'lavanda')
  assert.equal(await evaluate(`fetch('/api/readings/me',{headers:${headers}}).then(r=>r.status)`), 200)
  assert.deepEqual(await evaluate(`fetch('/api/readings/me',{headers:${headers}}).then(r=>r.json())`), [])
  await screenshot('live-welcome-390')
  await evaluate(`fetch('/api/profiles/me/onboarding/theme',{method:'PATCH',headers:{...${headers},'Content-Type':'application/json'},body:JSON.stringify({theme:'dark'})}).then(r=>r.json())`)
  // A new document must restore the server preference even over a different local selection.
  await evaluate(`localStorage.setItem('libria_theme','lavanda')`)
  await page.call('Page.reload')
  await until(`document.documentElement.dataset.theme==='dark' && document.querySelector('.initial-literary-dna')`)
  assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth`), true)
  console.log('PASS real React/FastAPI/PostgreSQL: registration, backend gate, reload/resume, all steps, zero favorites, completion without Gemini, library unchanged, server theme restored')
} finally {
  page.socket.close(); await browser.call('Target.disposeBrowserContext', { browserContextId: context }); browser.socket.close()
}
