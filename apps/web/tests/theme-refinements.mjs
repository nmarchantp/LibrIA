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
 await send('Page.navigate',{url:`${app}/tests/fixtures/theme-refinements.html?role=admin`})
 await until(`Boolean(document.querySelector('.reader-profile'))`)
 await mkdir(new URL('../../../artifacts/theme-refinements/',import.meta.url),{recursive:true})
 const paths=['/','/profile','/profile?tab=library','/reading/book-fixture','/books?q=Historias','/events','/recommendations','/settings','/admin/profiles']
 for(const theme of ['dark','lavanda']) {
  await evaluate(`import('/src/theme/themes.js').then(m=>m.applyTheme('${theme}'))`)
  const contrast=await evaluate(`(()=>{
   const shell=document.querySelector('.social-shell');const probe=document.createElement('div');probe.style.cssText='position:fixed;left:-2000px;top:0;width:200px';probe.innerHTML='<button class="button primary">Principal</button><button class="button">Secundario</button><button class="button danger">Eliminar</button><input value="Texto" />';shell.append(probe);
   const c=document.createElement('canvas');c.width=c.height=1;const ctx=c.getContext('2d');const lum=color=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=color;ctx.fillRect(0,0,1,1);const rgb=[...ctx.getImageData(0,0,1,1).data].slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722};const ratio=(a,b)=>{a=lum(a);b=lum(b);return(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};
   const values=[...probe.querySelectorAll('button,input')].map(e=>{const s=getComputedStyle(e);return {kind:e.className||'input',text:ratio(s.color,s.backgroundColor),border:ratio(s.borderTopColor,s.backgroundColor),color:s.color,bg:s.backgroundColor}});probe.remove();return values})()`)
  for(const sample of contrast){assert.ok(sample.text>=4.5,`${theme} ${sample.kind}: ${sample.text}`);if(sample.kind==='input'||sample.kind==='button')assert.ok(sample.border>=3,`${theme} ${sample.kind} border: ${sample.border}`)}
  console.log(theme,JSON.stringify(contrast))
  for(const [width,height] of [[1440,1000],[1024,768],[768,1024],[390,844],[320,568],[844,390]]) {
   await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<768})
   for(const path of paths){
    await evaluate(`history.pushState({},'',${JSON.stringify(path)});window.dispatchEvent(new PopStateEvent('popstate'))`)
    await until(`Boolean(document.querySelector('main#main-content>*'))`)
    await new Promise(r=>setTimeout(r,140))
    assert.equal(exceptions.length,0,`${theme} ${path}: ${exceptions.join(';')}`)
    assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth+1`),true,`${theme} ${width} ${path} overflows`)
    if((width===1440||width===390)&&['/profile','/books?q=Historias','/settings','/admin/profiles'].includes(path)){
     const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(new URL(`../../../artifacts/theme-refinements/${theme}-${width}-${path.split('?')[0].replaceAll('/','')}.png`,import.meta.url),Buffer.from(screenshot.result.data,'base64'))
    }
   }
  }
  await evaluate(`history.pushState({},'','/profile');window.dispatchEvent(new PopStateEvent('popstate'))`)
  await until(`Boolean(document.querySelector('.reader-profile'))`)
  await until(`Boolean(document.querySelector('.reader-about-edit-toggle'))`)
  await evaluate(`document.querySelector('.reader-about-edit-toggle').click()`)
  await until(`Boolean(document.querySelector('[aria-label="Editar Mi historia"]'))`)
  await evaluate(`document.querySelector('[aria-label="Editar Mi historia"]').click()`)
  await until(`Boolean(document.querySelector('.reader-profile-modal[open] textarea'))`)
  const modal=await evaluate(`(()=>{const e=document.querySelector('.reader-profile-modal'),r=e.getBoundingClientRect(),f=e.querySelector('textarea');f.focus();return {left:r.left,right:r.right,top:r.top,viewport:innerWidth,border:getComputedStyle(f).borderTopColor,outline:getComputedStyle(f).outlineStyle}})()`)
  assert.ok(modal.left>=0&&modal.right<=modal.viewport&&modal.top>=0,`${theme} modal geometry`)
  assert.equal(modal.outline,'solid')
  await evaluate(`document.querySelector('.reader-profile-modal [aria-label="Cerrar editor"]').click()`)
  await until(`!document.querySelector('.reader-profile-modal')`)
 }
 const defaults=await evaluate(`(async()=>{const m=await import('/src/theme/visualPreferences.js');const savedTheme=localStorage.getItem('libria_theme'),savedMotion=localStorage.getItem(m.magicalBackgroundMotionStorageKey);const result={};for(const theme of ['dark','lavanda','otono']){localStorage.setItem('libria_theme',theme);localStorage.removeItem(m.magicalBackgroundMotionStorageKey);result[theme]=m.readMagicalBackgroundMotion()}localStorage.setItem(m.magicalBackgroundMotionStorageKey,'true');result.explicit=m.readMagicalBackgroundMotion();if(savedTheme===null)localStorage.removeItem('libria_theme');else localStorage.setItem('libria_theme',savedTheme);if(savedMotion===null)localStorage.removeItem(m.magicalBackgroundMotionStorageKey);else localStorage.setItem(m.magicalBackgroundMotionStorageKey,savedMotion);return result})()`)
 assert.deepEqual(defaults,{dark:false,lavanda:false,otono:true,explicit:true})
 console.log('PASS: two themes, nine app views, six viewport sizes, text contrast >=4.5:1, control boundaries >=3:1; no runtime exceptions or horizontal overflow')
}finally{socket.close();await browserCall('Target.disposeBrowserContext',{browserContextId});browser.close()}
