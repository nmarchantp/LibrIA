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
const exceptions=[]
socket.addEventListener('message',event=>{const m=JSON.parse(event.data);if(m.method==='Runtime.exceptionThrown')exceptions.push(m.params.exceptionDetails.text+' '+m.params.exceptionDetails.exception?.description)})
try {
 await send('Runtime.enable')
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false})
 await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]})
 await send('Page.navigate',{url:`${app}/tests/fixtures/theme-refinements.html?role=admin&scene=mural`})
 await until(`Boolean(document.querySelector('.reader-profile'))`)
 await evaluate(`localStorage.setItem('libria_theme','dark-blood');window.dispatchEvent(new StorageEvent('storage',{key:'libria_theme',newValue:'dark-blood'}));localStorage.setItem('libriaverse-magical-background','true');window.dispatchEvent(new StorageEvent('storage',{key:'libriaverse-magical-background',newValue:'true'}))`)
 await evaluate(`localStorage.setItem('libriaverse-magical-background-motion','true');window.dispatchEvent(new StorageEvent('storage',{key:'libriaverse-magical-background-motion',newValue:'true'}))`)
 await until(`document.getAnimations().some(a=>a.animationName==='blood-candlelight')`)
 const live=await evaluate(`(async()=>{const e=document.querySelector('.sidebar-candle-flame-shape');const before=getComputedStyle(e).transform;await new Promise(r=>setTimeout(r,350));return {before,after:getComputedStyle(e).transform,opacity:getComputedStyle(e).opacity,reduced:matchMedia('(prefers-reduced-motion:reduce)').matches}})()`)
 assert.equal(live.reduced,true)
 assert.notEqual(live.before,live.after,'flame really moves over wall clock time with OS reduced motion')
 assert.equal(live.opacity,'1')
 const light=await evaluate(`(()=>{const e=document.querySelector('.sidebar-account'),s=getComputedStyle(e,'::before'),a=document.getAnimations().find(a=>a.animationName==='blood-candlelight');a.pause();a.currentTime=0;const low=getComputedStyle(e,'::before').opacity;a.currentTime=1900*.71;const high=getComputedStyle(e,'::before').opacity;return {low,high,pointer:s.pointerEvents}})()`)
 assert.notEqual(light.low,light.high,'light intensity changes')
 assert.equal(light.pointer,'none')
 const point=await evaluate(`(()=>{const r=document.querySelector('.sidebar-candle-hit').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`)
 await send('Input.dispatchMouseEvent',{type:'mouseMoved',...point})
 await until(`getComputedStyle(document.querySelector('.sidebar-account'),'::before').animationName==='blood-candle-gust'`)
 assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-candle-flame-shape')).animationName`),'blood-flame-gust','hover perturbs flame')
 const shape=await evaluate(`(()=>{const e=document.querySelector('.sidebar-candle-flame-shape'),a=document.getAnimations().find(a=>a.animationName==='blood-flame-gust');a.pause();a.currentTime=0;const first=getComputedStyle(e).transform;a.currentTime=220;return {first,second:getComputedStyle(e).transform,opacity:getComputedStyle(e).opacity}})()`)
 assert.notEqual(shape.first,shape.second,'flame changes geometry rather than only opacity')
 assert.equal(shape.opacity,'1','flame stays lit')
 await mkdir(new URL('../../../artifacts/blood-candlelight/',import.meta.url),{recursive:true})
 const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
 await writeFile(new URL('../../../artifacts/blood-candlelight/desktop.png',import.meta.url),Buffer.from(screenshot.result.data,'base64'))

 await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:500,y:30})
 await until(`getComputedStyle(document.querySelector('.sidebar-account'),'::before').animationName==='blood-candlelight'`)
 await evaluate(`localStorage.setItem('libriaverse-magical-background-motion','false');window.dispatchEvent(new StorageEvent('storage',{key:'libriaverse-magical-background-motion',newValue:'false'}))`)
 await until(`document.querySelector('.sidebar-candle-reactor').dataset.animated==='false'`)
 assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-account'),'::before').animationName`),'none','movement switch stops glow')
 assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-candle-flame-shape')).animationName`),'none','movement switch stops flame')
 await evaluate(`localStorage.setItem('libriaverse-magical-background','false');window.dispatchEvent(new StorageEvent('storage',{key:'libriaverse-magical-background',newValue:'false'}))`)
 await until(`!document.querySelector('.profile-starfield')`)
 assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-account'),'::before').content`),'none','background switch removes glow')
 assert.equal(exceptions.length,0,exceptions.join(';'))
 console.log('PASS pointer-driven flame and light perturbation, candlelight intensity animation, pointer transparency, reduced motion and magical background switch')
} finally {socket.close();await browserCall('Target.disposeBrowserContext',{browserContextId});browser.close()}
