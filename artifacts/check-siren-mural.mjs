import assert from 'node:assert/strict'

const cdp = process.env.CDP_URL || 'http://127.0.0.1:9224'
const app = process.env.APP_URL || 'http://127.0.0.1:5173'
const target = await (await fetch(`${cdp}/json/new?about:blank`, { method:'PUT' })).json()
const socket = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => { socket.onopen=resolve; socket.onerror=reject })
let sequence=0
const pending=new Map()
socket.onmessage=event=>{
  const message=JSON.parse(event.data)
  if (pending.has(message.id)) {
    const {resolve,reject}=pending.get(message.id)
    pending.delete(message.id)
    if(message.error) reject(Error(JSON.stringify(message.error)))
    else resolve(message.result)
  }
}
const send=(method,params={})=>new Promise((resolve,reject)=>{
  pending.set(++sequence,{resolve,reject})
  socket.send(JSON.stringify({id:sequence,method,params}))
})
async function evaluate(expression) {
  const result=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})
  if(result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails))
  return result.result.value
}
async function until(expression) {
  for(let attempt=0;attempt<100;attempt++) {
    if(await evaluate(expression)) return
    await new Promise(resolve=>setTimeout(resolve,50))
  }
  throw Error(`Timed out: ${expression}`)
}
try {
 await send('Emulation.setDeviceMetricsOverride',{width:1920,height:1000,deviceScaleFactor:1,mobile:false});
 await send('Page.navigate',{url:`${app}/tests/fixtures/theme-refinements.html?role=admin&scene=mural`});
 await until(`Boolean(document.querySelector('.reader-profile'))`);
 await evaluate(`history.pushState(null,'','/');window.dispatchEvent(new PopStateEvent('popstate'))`);
 await until(`Boolean(document.querySelector('.mural-heading'))`);
 await evaluate(`import('/src/theme/themes.js').then(m=>m.applyTheme('canto-sirenas'))`);
 await evaluate(`(async()=>{const img=new Image();img.src='/images/themes/canto-sirenas/banner-v2.png';await img.decode()})()`);
 const styles=await evaluate(`(()=>{const s=getComputedStyle(document.querySelector('.profile-starfield'),'::before');return {width:s.width,mask:s.maskImage,position:s.backgroundPosition}})()`);
 assert.ok(styles.mask.includes('18%'));
 assert.ok(parseFloat(styles.width)<=912);
 const shot=await send('Page.captureScreenshot',{format:'png',clip:{x:0,y:0,width:1920,height:440,scale:1}});
 await (await import('node:fs/promises')).writeFile(new URL('./siren-mural-fade.png',import.meta.url),Buffer.from(shot.data,'base64'));
 console.log('PASS: mural image bounds and left fade',styles);
}finally{socket.close();await fetch(`${cdp}/json/close/${target.id}`)}