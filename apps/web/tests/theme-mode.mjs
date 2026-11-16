import assert from 'node:assert/strict'
const cdp = process.env.CDP_URL || 'http://127.0.0.1:9224'
const app = 'http://127.0.0.1:5173'
const target = await (await fetch(`${cdp}/json/new?about:blank`, { method: 'PUT' })).json()
const socket = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
let sequence = 0
const pending = new Map()
socket.onmessage = event => { const data = JSON.parse(event.data); if (pending.has(data.id)) { pending.get(data.id)(data); pending.delete(data.id) } }
const send = (method, params = {}) => new Promise(resolve => { pending.set(++sequence, resolve); socket.send(JSON.stringify({ id: sequence, method, params })) })
async function evaluate(expression) { const value = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }); if (value.result?.exceptionDetails) throw Error(JSON.stringify(value.result.exceptionDetails)); return value.result.result.value }
async function until(expression) { for (let n=0;n<600;n++) { if(await evaluate(expression))return; await new Promise(r=>setTimeout(r,50)) } throw Error('Timed out: '+expression) }
try {
 await send('Page.navigate',{url:`${app}/tests/fixtures/theme-mode.html?reset=1`})
 await until(`document.documentElement.dataset.theme==='dark' && Boolean(document.querySelector('button'))`)
 assert.equal(await evaluate(`getComputedStyle(document.documentElement).colorScheme`),'dark')
 assert.equal(await evaluate(`Boolean(document.querySelector('button svg.lucide-sun'))`),true)
 await evaluate(`document.querySelector('button').click()`)
 await until(`document.documentElement.dataset.theme==='lavanda' && localStorage.getItem('libria_theme')==='lavanda'`)
 assert.equal(await evaluate(`getComputedStyle(document.documentElement).colorScheme`),'light')
 assert.equal(await evaluate(`Boolean(document.querySelector('button svg.lucide-moon'))`),true)
 await send('Page.reload')
 await until(`document.documentElement.dataset.theme==='lavanda' && Boolean(document.querySelector('button'))`)
 await evaluate(`document.querySelector('button').click()`)
 await until(`document.documentElement.dataset.theme==='dark'`)
 for(const width of [1440,768,390,320]){
  await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<768})
  const hit=await evaluate(`(()=>{const r=document.querySelector('button').getBoundingClientRect();return {width:r.width,height:r.height,overflow:document.documentElement.scrollWidth>innerWidth}})()`)
  assert.ok(hit.width>=44&&hit.height>=44);assert.equal(hit.overflow,false)
 }
 await evaluate(`localStorage.setItem('libria_theme','invalid-theme')`)
 await send('Page.reload');await until(`document.documentElement.dataset.theme==='dark'`)
 await evaluate(`localStorage.setItem('libria_theme','dark-rosado')`)
 await send('Page.reload');await until(`document.documentElement.dataset.theme==='dark-rosado' && Boolean(document.querySelector('button'))`)
 await evaluate(`document.querySelector('button').click()`);await until(`document.documentElement.dataset.theme==='lavanda'`)
 console.log('PASS: default dark theme, light/dark quick toggle, persistence, invalid fallback, other dark variants and 44px targets at 4 widths')
} finally { socket.close(); await fetch(`${cdp}/json/close/${target.id}`) }
