import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
const cdp = process.env.CDP_URL || 'http://127.0.0.1:9224'
const app = 'http://127.0.0.1:5173'
const version = await (await fetch(`${cdp}/json/version`)).json()
const browser = new WebSocket(version.webSocketDebuggerUrl)
await new Promise(resolve => { browser.onopen=resolve })
let browserSequence=0
const browserPending=new Map()
browser.onmessage=event=>{const message=JSON.parse(event.data);browserPending.get(message.id)?.(message.result)}
const browserCall=(method,params={})=>new Promise(resolve=>{const id=++browserSequence;browserPending.set(id,resolve);browser.send(JSON.stringify({id,method,params}))})
const {browserContextId}=await browserCall('Target.createBrowserContext')
const {targetId}=await browserCall('Target.createTarget',{url:'about:blank',browserContextId})
const target=(await (await fetch(`${cdp}/json/list`)).json()).find(item=>item.id===targetId)
const socket = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
let sequence = 0
const pending = new Map()
socket.onmessage = event => { const data = JSON.parse(event.data); if (pending.has(data.id)) { pending.get(data.id)(data); pending.delete(data.id) } }
const send = (method, params = {}) => new Promise(resolve => { pending.set(++sequence, resolve); socket.send(JSON.stringify({ id: sequence, method, params })) })
async function evaluate(expression) { const value = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }); if (value.result?.exceptionDetails) throw Error(JSON.stringify(value.result.exceptionDetails)); return value.result.result.value }
async function until(expression) { for (let n=0;n<600;n++) { if(await evaluate(`Boolean(${expression})`))return; await new Promise(r=>setTimeout(r,50)) } throw Error('Timed out: '+expression+' '+await evaluate('document.body.innerText')) }
async function fill(selector,value) { await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}))})()`); await new Promise(r=>setTimeout(r,30)) }

try {
  await send('Page.enable')
  await send('Runtime.enable')
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false})
  await send('Page.navigate',{url:`${app}/tests/fixtures/welcome-guide.html`})
  await until(`document.querySelector('.welcome-guide') && location.search==='?tab=analysis'`)
  assert.equal(await evaluate(`document.querySelector('.welcome-guide-summary').textContent.includes('Fantas\u00eda')`),true)
  assert.equal(await evaluate(`document.querySelector('.initial-literary-dna').hasAttribute('data-welcome-focus')`),true)
  await evaluate(`document.querySelector('.welcome-guide .primary').click()`)
  await until(`location.pathname==='/books' && document.querySelector('.catalog-search-input input') && !document.querySelector('.welcome-guide').getAttribute('aria-busy').includes('true')`)
  await fill('.catalog-search-input input','Orgullo y prejuicio')
  await until(`document.querySelector('.welcome-guide h2')?.textContent.includes('correcto')`)
  await evaluate(`document.querySelector('.catalog-result-card').click()`)
  await until(`location.pathname.startsWith('/books/') && document.querySelector('.detail-library-action') && document.querySelector('.welcome-guide h2')?.textContent.includes('Gu\u00e1rdalo')`)
  await evaluate(`document.querySelector('button.detail-library-action').click()`)
  await until(`location.search==='?tab=library' && document.querySelector('.reader-book-cover') && document.querySelector('.welcome-guide h2')?.textContent.includes('lugar')`)
  assert.equal(await evaluate(`window.welcomeTest.calls.filter(c=>c.path==='/readings/library'&&c.method==='POST').length`),1)
  assert.equal(await evaluate(`document.querySelector('.reader-book-status').textContent.includes('Pendiente')`),true)
  await evaluate(`document.querySelector('.welcome-guide .primary').click()`)
  await until(`location.pathname.startsWith('/library/') && document.querySelector('.reading-status-picker') && document.querySelector('.welcome-guide h2')?.textContent.includes('empezar')`)
  await evaluate(`document.querySelector('.welcome-guide .primary').click()`)
  await until(`document.querySelector('.welcome-guide h2')?.textContent.includes('avance')`)
  await send('Page.navigate',{url:`${app}/tests/fixtures/welcome-guide.html`})
  await until(`document.querySelector('.welcome-guide h2')?.textContent.includes('avance') && document.querySelector('.compact-progress-editor')`)
  await until(`document.querySelector('.reading-status-strip')?.textContent.includes('Pendiente')`) // The guide never changes the reading status.
  await evaluate(`document.querySelector('.welcome-guide .primary').click()`)
  await until(`document.querySelector('.welcome-guide h2')?.textContent.includes('Conserva') && document.querySelector('[data-guide-notebook]')?.getAttribute('aria-pressed')==='true'`)
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true})
  await evaluate(`new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))`)
  assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth`),true,'The guide fits on mobile')
  await mkdir(new URL('../../../artifacts/onboarding-wizard/',import.meta.url),{recursive:true})
  {const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});await writeFile(new URL('../../../artifacts/onboarding-wizard/welcome-guide-mobile.png',import.meta.url),Buffer.from(shot.result.data,'base64'))}
  await evaluate(`document.querySelector('.welcome-guide .primary').click()`)
  await until(`!document.querySelector('.welcome-guide') && JSON.parse(sessionStorage.getItem('guide-test-progress')).step==='completed'`)
  await send('Page.navigate',{url:`${app}/tests/fixtures/welcome-guide.html`})
  await until(`document.querySelector('.initial-literary-dna')`)
  assert.equal(await evaluate(`Boolean(document.querySelector('.welcome-guide'))`),false,'Completed guide does not replay')
  await evaluate(`window.dispatchEvent(new Event('libria:start-welcome-guide'))`)
  await until(`document.querySelector('.welcome-guide') && location.search==='?tab=analysis'`)
  await evaluate(`document.querySelector('.welcome-guide .text').click()`)
  await until(`!document.querySelector('.welcome-guide') && JSON.parse(sessionStorage.getItem('guide-test-progress')).step==='dismissed'`)
  console.log('PASS: questionnaire summary, catalog search, real book addition, pending library entry, reading controls, progress, notebook, reload resume, mobile, completion and skip')
} finally {
  await browserCall('Target.disposeBrowserContext',{browserContextId})
  socket.close(); browser.close()
}
