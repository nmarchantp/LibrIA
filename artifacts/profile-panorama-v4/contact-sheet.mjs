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
const {readFile,writeFile}=await import('node:fs/promises');
try {
 await send('Page.navigate',{url:`${app}/tests/fixtures/theme-refinements.html?role=admin&scene=mural`});
 await until(`Boolean(document.querySelector('.reader-profile'))`);
 const records=JSON.parse(await readFile(new URL('./assets.json',import.meta.url),'utf8'));
 const data=await evaluate(`(async()=>{const rows=${JSON.stringify(records)};const canvas=document.createElement('canvas');canvas.width=1800;canvas.height=Math.ceil(rows.length/3)*225;const ctx=canvas.getContext('2d');ctx.fillStyle='#211c25';ctx.fillRect(0,0,canvas.width,canvas.height);await Promise.all(rows.map(async(row,index)=>{const img=new Image();img.src='/'+row.output.split('public/')[1];await img.decode();const x=index%3*600,y=Math.floor(index/3)*225;ctx.drawImage(img,x,y+25,600,200);ctx.fillStyle='#fff';ctx.font='16px sans-serif';ctx.fillText(row.id,x+10,y+19)}));return canvas.toDataURL('image/jpeg',.9)})()`);
 await writeFile(new URL('./contact-sheet.jpg',import.meta.url),Buffer.from(data.split(',')[1],'base64'));
 console.log('Reviewed sources:',records.length);
}finally{socket.close();await fetch(`${cdp}/json/close/${target.id}`)}