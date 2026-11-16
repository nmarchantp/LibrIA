import assert from 'node:assert/strict'
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
 await send('Page.navigate',{url:`${app}/tests/fixtures/theme-refinements.html?role=admin&scene=mural`})
 await until(`Boolean(document.querySelector('.reader-profile'))`)
 const themes=await evaluate(`import('/src/theme/themes.js').then(m=>m.themes.map(t=>t.id))`)
 for(const theme of themes) {
  await evaluate(`localStorage.setItem('libria_theme','${theme}');window.dispatchEvent(new StorageEvent('storage',{key:'libria_theme',newValue:'${theme}'}))`)
  await until(`document.documentElement.dataset.theme==='${theme}'`)
  for(const [width,height] of [[1440,1000],[1920,1080],[1024,768]]) {
   await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false})
   const layout=await evaluate(`(()=>{const nav=document.querySelector('.sidebar-navigation'),account=nav.querySelector('.sidebar-account'),art=getComputedStyle(nav,'::after');return {margin:getComputedStyle(account).marginTop,artTop:art.marginTop,artBottom:art.marginBottom,flex:art.flex,background:art.backgroundImage,svg:!!nav.querySelector('.sidebar-candle-art image'),navScroll:nav.querySelector('.social-nav').scrollHeight>nav.querySelector('.social-nav').clientHeight+1}})()`)
   assert.equal(layout.margin,'0px',`${theme} ${width}: no gap after artwork`)
   assert.ok(Number.parseFloat(layout.artTop)>=0,`${theme} ${width}: spare space above artwork`)
   assert.equal(layout.artBottom,'0px')
   assert.equal(layout.flex,'0 1 340px')
   const pendingArt=await evaluate(`import('/src/theme/literaryThemes.js').then(m=>m.literaryThemes.some(t=>t.id==='${theme}'&&!t.art))`)
   assert.ok(pendingArt ? !layout.background.includes('url(') : layout.background.includes('url(')||layout.svg,`${theme}: available artwork mounted, pending artwork has no broken URL`)
   assert.equal(layout.navScroll,false,`${theme}: navigation doesn't shrink`)
  }
 }
 assert.equal(exceptions.length,0,exceptions.join(';'))
 console.log('PASS sidebar artwork directly before account in all 24 themes at three desktop/tablet sizes')
} finally {socket.close();await browserCall('Target.disposeBrowserContext',{browserContextId});browser.close()}
