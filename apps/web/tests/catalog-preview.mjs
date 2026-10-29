// Real browser, isolated fixture with all HTTP mocked; never contacts a database.
import assert from 'node:assert/strict'
import fs from 'node:fs'
const cdp=process.env.CDP_URL || 'http://127.0.0.1:9236'
const app=process.env.VITE_URL || 'http://127.0.0.1:5186'
const target=await (await fetch(`${cdp}/json/new?about:blank`,{method:'PUT'})).json()
const ws=new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject})
let sequence=0
const pending=new Map()
ws.onmessage=event=>{const message=JSON.parse(event.data);if(pending.has(message.id)){pending.get(message.id)(message);pending.delete(message.id)}}
const send=(method,params={})=>new Promise(resolve=>{pending.set(++sequence,resolve);ws.send(JSON.stringify({id:sequence,method,params}))})
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.result.exceptionDetails)throw Error(JSON.stringify(r.result.exceptionDetails));return r.result.result.value}
async function until(expression){for(let i=0;i<100;i++){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,50))}throw Error(`Timed out: ${expression}`)}
async function click(label,index=0){await evaluate(`[...document.querySelectorAll('button')].filter(b=>b.textContent===${JSON.stringify(label)})[${index}].click()`)}
async function navigate(query){await send('Page.navigate',{url:`${app}/tests/fixtures/catalog-preview.html?${query}`})}
try {
  await send('Emulation.setDeviceMetricsOverride',{width:1280,height:960,deviceScaleFactor:1,mobile:false})
  await navigate('role=lector&admin=true')
  await until("document.querySelector('h1')?.textContent==='Comparación de obras'")
  assert.equal(await evaluate("document.querySelector('#catalog-title-query').placeholder"),'Ej.: Cien años de soledad')
  assert.notEqual(await evaluate("getComputedStyle(document.querySelector('.catalog-panel')).backgroundColor"),'rgba(0, 0, 0, 0)')
  fs.mkdirSync('../../tmp',{recursive:true})
  fs.writeFileSync('../../tmp/catalog-ui-desktop.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).result.data,'base64'))
  await evaluate("(()=>{const input=document.querySelector('#catalog-title-query');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'Obra');input.dispatchEvent(new Event('input',{bubbles:true}))})()")
  await click('Buscar');await until("document.querySelectorAll('.catalog-results>li').length===2")
  await click('Seleccionar origen',0);await click('Seleccionar destino canónico',1)
  await click('Comparar');await until("document.body.textContent.includes('Impacto previsto')")
  await click('Simular fusión');await until("document.body.textContent.includes('preview-fixture')")
  assert.equal(await evaluate("[...document.querySelectorAll('button')].some(b=>/confirmar|ejecutar fusión/i.test(b.textContent))"),false)
  await evaluate('window.catalogTest.fail=true')
  await click('Simular fusión');await until("document.querySelector('[role=alert]')?.textContent.includes('recuperable')")
  assert.equal(await evaluate("document.body.textContent.includes('preview-fixture')"),false)
  assert.equal(await evaluate("window.catalogTest.calls.some(p=>/execute|confirm|gemini/.test(p))"),false)
  await navigate('role=admin&admin=false')
  await until("document.body.textContent.includes('Acceso denegado')")
  await navigate('role=lector&admin=true&preview=false')
  await until("document.body.textContent.includes('Comparación administrativa deshabilitada')")
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true})
  await navigate('role=lector&admin=true&theme=lavanda')
  await until("document.querySelector('#catalog-title-query') !== null")
  assert.equal(await evaluate('document.documentElement.scrollWidth<=window.innerWidth'),true,'Mobile layout must not overflow horizontally')
  fs.writeFileSync('../../tmp/catalog-ui-mobile.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).result.data,'base64'))
  console.log('PASS: effective permissions, role-only denial, disabled flag, search, compare, preview, recovery, no execution control')
} finally { await send('Page.close');ws.close() }
