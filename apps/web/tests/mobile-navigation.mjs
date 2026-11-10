// Isolated React fixture and Chrome CDP: no backend writes.
import assert from 'node:assert/strict'
import { mkdir, writeFile, readFile } from 'node:fs/promises'
const cdp=process.env.CDP_URL || 'http://127.0.0.1:9224'
const app=process.env.VITE_URL || 'http://localhost:5173'
// Optional pre-change CSS enables exact desktop comparison during review.
const originalCss=process.env.NAVIGATION_BASELINE_CSS ? (await readFile(process.env.NAVIGATION_BASELINE_CSS,'utf8'))+'\n.mobile-nav-backdrop,.mobile-drawer-heading {display:none}' : null
const target=await (await fetch(`${cdp}/json/new?about:blank`,{method:'PUT'})).json()
const ws=new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject})
let seq=0;const pending=new Map()
ws.onmessage=event=>{const m=JSON.parse(event.data);if(m.id){pending.get(m.id)?.(m);pending.delete(m.id)}}
const send=(method,params={})=>new Promise(resolve=>{pending.set(++seq,resolve);ws.send(JSON.stringify({id:seq,method,params}))})
const evaluate=async expression=>{const m=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(m.error||m.result?.exceptionDetails)throw Error(JSON.stringify(m));return m.result.result.value}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms))
async function until(expression){for(let i=0;i<100;i++){if(await evaluate(expression))return;await pause(50)}throw Error(`Timeout: ${expression}`)}
const resize=async(width,height=900)=>{await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<=700});await pause(60)}
const key=async(key,code=key,extra={})=>{await send('Input.dispatchKeyEvent',{type:'keyDown',key,code,...extra});await send('Input.dispatchKeyEvent',{type:'keyUp',key,code,...extra})}
async function click(selector){const p=await evaluate(`(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...p});await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...p});await pause(240)}
const open=async()=>{await click('.mobile-nav-toggle');assert.equal(await evaluate(`document.querySelector('.mobile-nav-toggle').getAttribute('aria-expanded')`),'true')}
const closed=async()=>{await pause(230);assert.equal(await evaluate(`document.querySelector('.mobile-nav-toggle').getAttribute('aria-expanded')`),'false');assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-navigation')).visibility`),'hidden');assert.equal(await evaluate(`document.body.style.overflow`),'')}
const desktopMetrics=`(()=>{const selectors=['.social-sidebar','.brand-link','.sidebar-navigation','.social-nav','.sidebar-account','.social-topbar','.header-greeting','.global-header-actions','.global-header-action','.navigation-tools'];return Object.fromEntries(selectors.map(selector=>{const e=document.querySelector(selector),r=e.getBoundingClientRect(),s=getComputedStyle(e);return [selector,{rect:[r.x,r.y,r.width,r.height],display:s.display,position:s.position,padding:s.padding,gap:s.gap,color:s.color,background:s.backgroundColor,border:s.border,shadow:s.boxShadow}]}))})()`
const artifacts=new URL('../../../artifacts/mobile-navigation/',import.meta.url)
const report=[]
try{
await mkdir(artifacts,{recursive:true})
await send('Emulation.setFocusEmulationEnabled',{enabled:true});await send('Page.bringToFront')
await resize(1440)
await send('Page.navigate',{url:`${app}/tests/fixtures/profile-modals.html?role=admin&group`})
await until(`!!document.querySelector('.navigation-tools')`)
await evaluate('document.fonts.ready.then(()=>true)')
const themes=await evaluate(`import('/src/theme/themes.js').then(m=>m.themes.map(t=>t.id))`)
for(const theme of themes){
 await evaluate(`import('/src/theme/themes.js').then(m=>m.applyTheme(${JSON.stringify(theme)}))`)
 for(const width of [320,375,390,430,768,1024,1440]){
  await resize(width)
  assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth`),true,`${theme}/${width}: horizontal overflow`)
  if(width>700){
   const current=await evaluate(desktopMetrics)
   if(originalCss){
   await evaluate(`(()=>{const style=document.querySelector('style[data-vite-dev-id$="/LayoutNavigation.css"]');window.currentNavigationCSS=style.textContent;style.textContent=${JSON.stringify(originalCss)}})()`)
   const original=await evaluate(desktopMetrics)
   await evaluate(`document.querySelector('style[data-vite-dev-id$="/LayoutNavigation.css"]').textContent=window.currentNavigationCSS`)
   assert.deepEqual(current,original,`${theme}/${width}: desktop changed`)
   }
   assert.equal(await evaluate(`getComputedStyle(document.querySelector('.mobile-nav-toggle')).display`),'none')
  }else{
   const fit=await evaluate(`(()=>{const brand=document.querySelector('.brand-link').getBoundingClientRect(),toggle=document.querySelector('.mobile-nav-toggle').getBoundingClientRect(),actions=document.querySelector('.global-header-actions').getBoundingClientRect();return {fits:brand.left>=0&&brand.width>60&&brand.right<=actions.left&&Math.abs(toggle.right-actions.right)<1&&actions.right<=innerWidth,buttons:[...document.querySelectorAll('.global-header-action,.mobile-nav-toggle')].every(e=>{const r=e.getBoundingClientRect();return r.width>=44&&r.height>=44&&r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=68})}})()`)
   assert.equal(fit.fits&&fit.buttons,true,`${theme}/${width}: header fit ${JSON.stringify(fit)}`)
   if(width===390&&['lavanda','dark'].includes(theme)){const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile(new URL(`${theme}-390-header.png`,artifacts),Buffer.from(shot.result.data,'base64'))}
   const headerBackground=await evaluate(`getComputedStyle(document.querySelector('.social-sidebar')).backgroundColor`)
   await evaluate(`window.scrollTo(0,200)`);await pause(60)
   assert.equal(await evaluate(`getComputedStyle(document.querySelector('.social-sidebar')).backgroundColor`),headerBackground,'Mobile header stays solid on scroll')
   assert.equal(await evaluate(`getComputedStyle(document.querySelector('.social-topbar .global-header-actions'),'::before').content`),'none','No mobile glass overlay on scroll')
   assert.equal(await evaluate(`(()=>{const probe=document.createElement('div');probe.style.background='var(--surface)';document.body.append(probe);const color=getComputedStyle(probe).backgroundColor;probe.remove();return getComputedStyle(document.querySelector('.social-sidebar')).backgroundColor===color})()`),true,'Opaque themed header')
   await evaluate(`window.scrollTo(0,0)`);await pause(60)
   const before=await evaluate(`document.querySelector('#main-content').getBoundingClientRect().top`)
   await open()
   assert.equal(await evaluate(`document.querySelector('#main-content').getBoundingClientRect().top`),before,'No layout shift')
   assert.equal(await evaluate(`(()=>{const e=document.querySelector('.sidebar-navigation'),r=e.getBoundingClientRect();return getComputedStyle(e).position==='fixed'&&r.left>=0&&Math.abs(r.right-innerWidth)<17&&r.top===0&&r.height===innerHeight&&e.getAttribute('role')==='dialog'&&e.getAttribute('aria-modal')==='true'&&document.activeElement===document.querySelector('.mobile-drawer-heading button')&&document.querySelector('.social-page-column').inert&&document.body.style.overflow==='hidden'})()`),true,'Drawer position, focus and scroll lock')
   await key('Tab','Tab',{shiftKey:true,modifiers:8,windowsVirtualKeyCode:9})
   assert.equal(await evaluate(`document.activeElement===document.querySelector('.logout-button')`),true,'Reverse focus trap')
   await key('Tab','Tab',{windowsVirtualKeyCode:9})
   assert.equal(await evaluate(`document.activeElement===document.querySelector('.mobile-drawer-heading button')`),true,'Forward focus trap')
   if(width===390&&['lavanda','dark'].includes(theme)){
    const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile(new URL(`${theme}-390.png`,artifacts),Buffer.from(shot.result.data,'base64'))
   }
   await key('Escape','Escape',{windowsVirtualKeyCode:27});await pause(40);assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth'),true,'No overflow during closing');await closed()
   assert.equal(await evaluate(`document.activeElement===document.querySelector('.mobile-nav-toggle')`),true,'Return focus')
  }
  report.push({theme,width,result:'pass',...(width>700?{desktop:await evaluate(desktopMetrics)}:{})})
 }
}
await resize(375)
await open();await click('.mobile-drawer-heading button');await closed()
await open();await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,x:5,y:200});await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,x:5,y:200});await closed()
await open();await click('#main-navigation a[href="/events"]');await closed();assert.equal(await evaluate('location.pathname'),'/events')
await resize(320,350);await open()
assert.equal(await evaluate(`(()=>{const e=document.querySelector('.sidebar-navigation');e.scrollTop=e.scrollHeight;return e.scrollHeight>e.clientHeight&&e.scrollTop>0})()`),true,'Internal vertical scroll')
await resize(1024);assert.equal(await evaluate(`!document.querySelector('.social-page-column').inert&&document.body.style.overflow===''&&document.querySelector('.sidebar-navigation').getAttribute('role')===null`),true,'Resize restores desktop')
await resize(390,500)
await evaluate(`history.pushState({},'','/profile');window.dispatchEvent(new PopStateEvent('popstate'))`)
await until(`!!document.querySelector('.reader-profile')`)
await evaluate(`window.scrollTo(0,200)`);await pause(100)
const scrollBefore=await evaluate('window.scrollY')
await open()
await send('Input.dispatchMouseEvent',{type:'mouseWheel',x:5,y:200,deltaY:200,deltaX:0});await pause(80)
assert.equal(await evaluate('window.scrollY'),scrollBefore,'Background does not scroll')
await key('Escape','Escape',{windowsVirtualKeyCode:27});await pause(40)
assert.equal(await evaluate(`new DOMMatrix(getComputedStyle(document.querySelector('.sidebar-navigation')).transform).m41>0`),true,'Drawer closes towards the right')
await closed();assert.equal(await evaluate('window.scrollY'),scrollBefore,'Restore exact background scroll')
await resize(390);await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});await open()
assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-navigation')).transitionDuration`),'0s','Reduced motion')
await key('Escape','Escape',{windowsVirtualKeyCode:27});await closed()
await writeFile(new URL('results.json',artifacts),JSON.stringify(report,null,2))
console.log('PASS 63 theme/viewport combinations; desktop at 768/1024/1440'+(originalCss?' matches original CSS;':';')+' 44px targets, no overflow/layout shift, focus trap/return, Escape/X/outside/navigation close, vertical scroll, resize cleanup and reduced motion.')
}finally{ws.close();await fetch(`${cdp}/json/close/${target.id}`)}
