import { readFile, writeFile } from 'node:fs/promises'
const cdp=process.env.CDP_URL||'http://127.0.0.1:9224'
const target=await(await fetch(`${cdp}/json/new?about:blank`,{method:'PUT'})).json()
const socket=new WebSocket(target.webSocketDebuggerUrl)
await new Promise(r=>{socket.onopen=r})
let seq=0;const pending=new Map()
socket.onmessage=e=>{const v=JSON.parse(e.data);pending.get(v.id)?.(v)}
const send=(method,params={})=>new Promise(r=>{const id=++seq;pending.set(id,r);socket.send(JSON.stringify({id,method,params}))})
try {
 for(const name of ['explorer-study-v2']){
  const source=await readFile(new URL(`./equinox-universe-sources/${name}.png`,import.meta.url))
  const sourceUrl='data:image/png;base64,'+source.toString('base64')
  const result=await send('Runtime.evaluate',{awaitPromise:true,returnByValue:true,expression:`(async()=>{const image=new Image();image.src=${JSON.stringify(sourceUrl)};await image.decode();const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0);return {data:canvas.toDataURL('image/webp',.86).split(',')[1],alpha:ctx.getImageData(0,0,1,1).data[3]}})()`})
  if(result.result.exceptionDetails)throw Error(JSON.stringify(result.result.exceptionDetails))
  const {data,alpha}=result.result.result.value
  const bytes=Buffer.from(data,'base64')
  await writeFile(new URL(`../apps/web/public/images/equinox-universe/${name}.webp`,import.meta.url),bytes)
  console.log(name,bytes.length,'bytes; corner alpha',alpha)
 }
}finally{socket.close();await fetch(`${cdp}/json/close/${target.id}`)}
