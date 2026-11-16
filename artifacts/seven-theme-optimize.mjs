import { readFile,writeFile,mkdir,stat } from 'node:fs/promises'
import { resolve } from 'node:path'
const root=resolve(new URL('../',import.meta.url).pathname.replace(/^\/([A-Z]:)/,'$1'))
const specifications=JSON.parse(await readFile(resolve(root,'apps/web/src/theme/literaryThemes.json'),'utf8'))
const tasks=JSON.parse(await readFile(resolve(root,'artifacts/seven-theme-refresh-prompts.json'),'utf8'))
const version=await(await fetch('http://127.0.0.1:9224/json/version')).json()
const browser=new WebSocket(version.webSocketDebuggerUrl);await new Promise(r=>browser.onopen=r)
let sequence=0;const pending=new Map();browser.onmessage=e=>{const m=JSON.parse(e.data);pending.get(m.id)?.(m.result)}
const call=(method,params={})=>new Promise(r=>{const id=++sequence;pending.set(id,r);browser.send(JSON.stringify({id,method,params}))})
const {browserContextId}=await call('Target.createBrowserContext')
const {targetId}=await call('Target.createTarget',{url:'about:blank',browserContextId})
const target=(await(await fetch('http://127.0.0.1:9224/json/list')).json()).find(t=>t.id===targetId)
const socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise(r=>socket.onopen=r)
let seq=0;const requests=new Map();socket.onmessage=e=>{const m=JSON.parse(e.data);requests.get(m.id)?.(m)}
const send=(method,params={})=>new Promise(r=>{const id=++seq;requests.set(id,r);socket.send(JSON.stringify({id,method,params}))})
const completed=new Set();const details={};let lastProgress=Date.now()
try {
 while(completed.size<tasks.length) {
  for(const {id,asset} of tasks) {
   const key=id+'/'+asset;if(completed.has(key))continue
   const original=resolve(root,'artifacts/theme-generation/originals','refresh-'+id,asset+'.png')
   const info=await stat(original).catch(()=>null);if(!info||Date.now()-info.mtimeMs<1000)continue
   const source='data:image/png;base64,'+(await readFile(original)).toString('base64')
   const bounds=asset==='banner'?[1800,700]:asset==='corner'?[600,750]:[600,900]
   const response=await send('Runtime.evaluate',{awaitPromise:true,returnByValue:true,expression:`(async()=>{const i=new Image();i.src=${JSON.stringify(source)};await i.decode();const scale=Math.min(1,${bounds[0]}/i.naturalWidth,${bounds[1]}/i.naturalHeight);const c=document.createElement('canvas');c.width=Math.round(i.naturalWidth*scale);c.height=Math.round(i.naturalHeight*scale);const ctx=c.getContext('2d');ctx.drawImage(i,0,0,c.width,c.height);let transparent=false;for(let x=0;x<c.width;x+=Math.max(1,Math.floor(c.width/20)))for(let y=0;y<c.height;y+=Math.max(1,Math.floor(c.height/20)))if(ctx.getImageData(x,y,1,1).data[3]<255)transparent=true;return {data:c.toDataURL('image/webp',.84).split(',')[1],width:c.width,height:c.height,transparent}})()`})
   if(response.result?.exceptionDetails)throw Error(JSON.stringify(response.result.exceptionDetails))
   const {data,...size}=response.result.result.value;const bytes=Buffer.from(data,'base64')
   if(asset==='sidebar-decoration'&&!size.transparent)throw Error(key+' has no transparency')
   const folder=resolve(root,'apps/web/public/images/theme-refresh-v1',id);await mkdir(folder,{recursive:true});await writeFile(resolve(folder,asset+'.webp'),bytes)
   details[id]??={};details[id][asset==='sidebar-decoration'?'sidebar':asset]={...size,bytes:bytes.length}
   completed.add(key);lastProgress=Date.now()
   await writeFile(resolve(root,'apps/web/src/theme/refreshedThemeAssets.json'),JSON.stringify(details,null,2)+'\n')
   console.log(completed.size+'/21',key,bytes.length+' bytes',size.width+'x'+size.height)
  }
  if(Date.now()-lastProgress>15*60*1000)throw Error('No new generated image in 15 minutes')
  if(completed.size<tasks.length)await new Promise(r=>setTimeout(r,1500))
 }
 console.log('PASS 21 optimized assets, proportional scaling and transparent sidebars')
} finally {socket.close();await call('Target.disposeBrowserContext',{browserContextId});browser.close()}
