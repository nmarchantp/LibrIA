import assert from 'node:assert/strict'
import { readFile,mkdir,writeFile } from 'node:fs/promises'
const root=new URL('../',import.meta.url)
const plans=JSON.parse(await readFile(new URL('artifacts/all-theme-footer-prompts.json',root),'utf8'))
const literature=JSON.parse(await readFile(new URL('apps/web/src/theme/literaryThemes.json',root),'utf8'))
const palette={dark:'#171421',lavanda:'#F4EFF9',otono:'#26190F',invierno:'#D9EAF7','rosa-antiguo':'#FFF2F8',bosque:'#073B2B','dark-dorado':'#070D1D','dark-blood':'#10090D','dark-rosado':'#25151F',...Object.fromEntries(literature.map(t=>[t.id,t.colors[0]]))}
const items=[{id:'dark',src:'/images/theme-refresh-v1/dark/footer-v2.webp'},...plans.map(t=>({id:t.id,src:`/images/theme-footers-v1/${t.id}/footer.webp`}))]
for(const item of items){const response=await fetch('http://127.0.0.1:5173'+item.src);assert.ok(response.ok,item.src);assert.match(response.headers.get('content-type'),/image\/webp/);item.data='data:image/webp;base64,'+Buffer.from(await response.arrayBuffer()).toString('base64')}
const version=await(await fetch('http://127.0.0.1:9224/json/version')).json()
const browser=new WebSocket(version.webSocketDebuggerUrl);await new Promise(r=>browser.onopen=r)
let seq=0;const pending=new Map();browser.onmessage=e=>{const m=JSON.parse(e.data);pending.get(m.id)?.(m.result)}
const call=(method,params={})=>new Promise(r=>{const id=++seq;pending.set(id,r);browser.send(JSON.stringify({id,method,params}))})
const {browserContextId}=await call('Target.createBrowserContext')
const {targetId}=await call('Target.createTarget',{url:'about:blank',browserContextId})
const target=(await(await fetch('http://127.0.0.1:9224/json/list')).json()).find(t=>t.id===targetId)
const ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r)
let sequence=0;const requests=new Map();ws.onmessage=e=>{const m=JSON.parse(e.data);requests.get(m.id)?.(m)}
const send=(method,params={})=>new Promise(r=>{const id=++sequence;requests.set(id,r);ws.send(JSON.stringify({id,method,params}))})
try{
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1120,deviceScaleFactor:1,mobile:false})
 const html='<style>body{margin:12px;background:#222;font:13px system-ui;display:grid;grid-template-columns:repeat(4,1fr);gap:10px}figure{margin:0;border:1px solid #777;border-radius:8px;overflow:hidden}figcaption{padding:5px;background:#333;color:white}img{width:100%;height:140px;object-fit:contain;display:block}</style>'+items.map(i=>`<figure style="background:${palette[i.id]}"><figcaption>${i.id}</figcaption><img alt="${i.id}" src="${i.data}"></figure>`).join('')
 const response=await send('Runtime.evaluate',{awaitPromise:true,returnByValue:true,expression:`(async()=>{document.open();document.write(${JSON.stringify(html)});document.close();await Promise.all([...document.images].map(i=>i.decode()));return [...document.images].map(i=>{const c=document.createElement('canvas');c.width=i.naturalWidth;c.height=i.naturalHeight;const x=c.getContext('2d');x.drawImage(i,0,0);return {id:i.alt,ratio:i.naturalWidth/i.naturalHeight,centerAlpha:x.getImageData(Math.floor(c.width*.4),Math.floor(c.height*.3),1,1).data[3]}})})()`})
 assert.ok(!response.result.exceptionDetails,JSON.stringify(response.result.exceptionDetails))
 for(const item of response.result.result.value){assert.ok(Math.abs(item.ratio-3)<.02,item.id+' ratio');assert.equal(item.centerAlpha,0,item.id+' transparent reading space')}
 await mkdir(new URL('artifacts/theme-footers/',root),{recursive:true})
 const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(new URL('artifacts/theme-footers/contact-sheet.png',root),Buffer.from(shot.result.data,'base64'))
 console.log('PASS 24 actual WebP URLs, image decoding, 3:1 proportions and transparent reading space; contact sheet saved')
}finally{ws.close();await call('Target.disposeBrowserContext',{browserContextId});browser.close()}
