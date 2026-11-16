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
 await send('Page.navigate',{url:`${app}/tests/fixtures/theme-refinements.html?role=admin&scene=mural`});
 await until(`Boolean(document.querySelector('.reader-profile-tabs'))`);
 await evaluate(`import('/src/theme/themes.js').then(m=>m.applyTheme('dark-blood'))`);
 const read = `(()=>{const s=getComputedStyle(document.querySelector('.mural-audiences button[aria-pressed="true"]'));return {background:s.backgroundImage,border:s.borderColor,color:s.color,shadow:s.boxShadow}})()`;
 const profile=await evaluate(read);
 await evaluate(`history.pushState(null,'','/');window.dispatchEvent(new PopStateEvent('popstate'))`);
 await until(`Boolean(document.querySelector('.mural-heading'))`);
 const mural=await evaluate(read);
 assert.deepEqual(profile,mural);
 console.log('PASS: profile selection matches Comunidad background, border, text and glow',profile);
}finally{socket.close();await fetch(`${cdp}/json/close/${target.id}`)}