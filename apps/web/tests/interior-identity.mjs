import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
const cdp = process.env.CDP_URL || 'http://127.0.0.1:9224'
const captureFolder = process.env.CAPTURE_FOLDER || 'interior-identity-after'
const app = 'http://127.0.0.1:5173'
const selectedThemes=process.env.INTERIOR_THEMES?.split(',')||['dark','lavanda','dark-blood','otono','rosa-antiguo','dark-dorado','bosque','invierno','dark-rosado']
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
 await send('Page.navigate',{url:`${app}/tests/fixtures/theme-refinements.html?role=admin${process.env.MURAL_SCENE ? '&scene=mural' : ''}`})
 await until(`Boolean(document.querySelector('.reader-profile'))`)
 await mkdir(new URL('../../../artifacts/'+captureFolder+'/',import.meta.url),{recursive:true})
 const paths=['/','/profile','/profile?tab=library','/reading/book-fixture','/books?q=Historias','/events','/recommendations','/settings','/admin/profiles']
 for(const theme of selectedThemes) {
  await evaluate(`localStorage.setItem('libria_theme','${theme}');window.dispatchEvent(new StorageEvent('storage',{key:'libria_theme',newValue:'${theme}'}))`)
  await until(`document.documentElement.dataset.theme==='${theme}'`)
  const expectedBanner=await evaluate(`import('/src/theme/profileBanners.js').then(m=>m.getProfileBanner('${theme}',true).src)`)
  await evaluate(`history.pushState({},'','/');window.dispatchEvent(new PopStateEvent('popstate'))`)
  await until(`Boolean(document.querySelector('.mural-heading'))`)
  const contrast=await evaluate(`(()=>{
   const shell=document.querySelector('.social-shell');const probe=document.createElement('div');probe.style.cssText='position:fixed;left:-2000px;top:0;width:200px';probe.innerHTML='<button class="button primary">Principal</button><button class="button primary" style="background:var(--primary-hover)">Hover</button><button class="button">Secundario</button><button class="button danger">Eliminar</button><input value="Texto" />';shell.append(probe);
   if('${theme}'==='otono')probe.insertAdjacentHTML('beforeend','<div class="catalog-result-card"><button class="button primary">Acción tarjeta</button><button class="button">Secundario tarjeta</button><input value="Texto tarjeta" /></div>');
   const c=document.createElement('canvas');c.width=c.height=1;const ctx=c.getContext('2d');const lum=color=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=color;ctx.fillRect(0,0,1,1);const rgb=[...ctx.getImageData(0,0,1,1).data].slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722};const ratio=(a,b)=>{a=lum(a);b=lum(b);return(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};
   const values=[...probe.querySelectorAll('button,input')].map(e=>{const s=getComputedStyle(e);return {kind:e.className||'input',text:ratio(s.color,s.backgroundColor),border:ratio(s.borderTopColor,s.backgroundColor),color:s.color,bg:s.backgroundColor}});probe.remove();return values})()`)
  if(!process.env.IDENTITY_BASELINE) for(const sample of contrast){assert.ok(sample.text>=4.5,`${theme} ${sample.kind}: ${sample.text}`);if(sample.kind==='input'||sample.kind==='button')assert.ok(sample.border>=3,`${theme} ${sample.kind} border: ${sample.border}`)}
  console.log(theme,JSON.stringify(contrast))
  if(!process.env.IDENTITY_BASELINE) {
   const footer=await evaluate(`(()=>{const s=getComputedStyle(document.querySelector('.profile-starfield'),'::after');return {image:s.backgroundImage,pointer:s.pointerEvents,animation:s.animationName}})()`)
   const expected=await evaluate(`import('/src/theme/themeFooters.js').then(m=>m.getThemeFooterAssets('${theme}'))`)
   assert.ok(footer.image.includes(expected.corner),`${theme}: own footer corner`)
   assert.ok(footer.image.includes(expected.strip),`${theme}: own horizontal footer strip`)
   assert.equal(footer.pointer,'none',`${theme}: footer does not intercept controls`)
   assert.equal(footer.animation,'none',`${theme}: static footer`)
  }
  if(['lavanda','dark','otono','invierno','rosa-antiguo','bosque','dark-dorado'].includes(theme)&&!process.env.IDENTITY_BASELINE) {
   const art=await evaluate(`({banner:getComputedStyle(document.querySelector('.profile-starfield'),'::before').backgroundImage,sidebar:getComputedStyle(document.querySelector('.sidebar-navigation'),'::after').backgroundImage,corner:getComputedStyle(document.querySelector('.reader-summary')).backgroundImage})`)
   for(const [role,file] of [['banner','banner'],['sidebar','sidebar-decoration'],['corner','corner']])assert.ok(art[role].includes('/images/theme-refresh-v1/'+theme+'/'+file+'.webp'),`${theme}: refreshed ${role}`)
  }
  for(const [width,height] of [[1440,1000],[1024,768],[768,1024],[390,844],[320,568],[844,390],[1920,1080]]) {
   await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<768})
   for(const path of paths){
    await evaluate(`history.pushState({},'',${JSON.stringify(path)});window.dispatchEvent(new PopStateEvent('popstate'))`)
    await until(`Boolean(document.querySelector('main#main-content>*'))`)
    await until(path.startsWith('/admin') ? `Boolean(document.querySelector('.admin-profiles'))` : `Boolean(document.querySelector('.literary-atmosphere'))`)
    if(path==='/profile'||path==='/profile?tab=library') await until(`(()=>{const image=document.querySelector('.reader-profile-cover img');return image?.getAttribute('src')===${JSON.stringify(expectedBanner)}&&image.complete&&image.naturalWidth>0})()`)
    await new Promise(r=>setTimeout(r,140))
    assert.equal(exceptions.length,0,`${theme} ${path}: ${exceptions.join(';')}`)
    assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth+1`),true,`${theme} ${width} ${path} overflows`)
    if(path==='/'&&!process.env.IDENTITY_BASELINE) {
     const scroll=await evaluate(`(async()=>{window.scrollTo(0,0);await new Promise(r=>requestAnimationFrame(r));const bg=document.querySelector('.social-viewport-background'),heading=document.querySelector('.mural-heading');const before={bg:bg.getBoundingClientRect().top,heading:heading.getBoundingClientRect().top};window.scrollTo(0,300);await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));const result={fixed:Math.abs(bg.getBoundingClientRect().top-before.bg)<2,contentMoved:heading.getBoundingClientRect().top<before.heading-20,height:bg.getBoundingClientRect().height,expected:innerHeight-(innerWidth<=700?68:0),scrolled:scrollY};window.scrollTo(0,0);return result})()`)
     assert.equal(scroll.fixed,true,`${theme} ${width}: scenery stays fixed during page scroll`)
     assert.ok(Math.abs(scroll.height-scroll.expected)<2,`${theme} ${width}: scenery limited to viewport`)
     if(scroll.scrolled>20)assert.equal(scroll.contentMoved,true,`${theme} ${width}: content scrolls above scenery`)
     const heading=await evaluate(`(()=>{const s=getComputedStyle(document.querySelector('.mural-heading'));return {image:s.backgroundImage,border:s.borderTopWidth,shadow:s.boxShadow}})()`)
     assert.deepEqual(heading,{image:'none',border:'0px',shadow:'none'},`${theme}: transparent mural heading`)
    }
    if(theme==='dark') {
     assert.equal(await evaluate(`getComputedStyle(document.querySelector('.social-shell')).getPropertyValue('--paper').trim()`),'#171421',`${path}: shared dark palette`)
     if(width>=768) assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-navigation'),'::after').backgroundImage.includes('theme-refresh-v1/dark/sidebar-decoration.webp')`),true,`${path}: shared sidebar art`)
    } else if(theme==='lavanda') {
     assert.equal(await evaluate(`getComputedStyle(document.querySelector('.social-shell')).getPropertyValue('--paper').trim().toUpperCase()`),'#F4EFF9',`${path}: preserved light background palette`)
     if(width>=768) assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-navigation'),'::after').backgroundImage.includes('theme-refresh-v1/lavanda/sidebar-decoration.webp')`),true,`${path}: light sidebar art`)
    } else if(theme==='dark-blood'&&!process.env.IDENTITY_BASELINE) {
     assert.equal(await evaluate(`getComputedStyle(document.querySelector('.social-shell')).getPropertyValue('--paper').trim().toUpperCase()`),'#10090D',`${path}: blood palette`)
     if(width>=768) assert.equal(await evaluate(`document.querySelector('.sidebar-candle-art image')?.getAttribute('href').includes('blood-universe/candle-books-v1.webp')`),true,`${path}: gothic sidebar art`)
    } else if(theme==='otono'&&!process.env.IDENTITY_BASELINE) {
     assert.equal(await evaluate(`getComputedStyle(document.querySelector('.social-shell')).getPropertyValue('--paper').trim().toUpperCase()`),'#26190F',`${path}: explorer background`)
     if(width>=768) assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-navigation'),'::after').backgroundImage.includes('theme-refresh-v1/otono/sidebar-decoration.webp')`),true,`${path}: explorer sidebar art`)
    } else if(theme==='rosa-antiguo'&&!process.env.IDENTITY_BASELINE) {
     assert.equal(await evaluate(`getComputedStyle(document.querySelector('.social-shell')).getPropertyValue('--paper').trim().toUpperCase()`),'#FFF2F8',`${path}: cotton background`)
     if(width>=768) assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-navigation'),'::after').backgroundImage.includes('theme-refresh-v1/rosa-antiguo/sidebar-decoration.webp')`),true,`${path}: supplied cotton artwork`)
    } else if(theme==='dark-dorado'&&!process.env.IDENTITY_BASELINE) {
     assert.equal(await evaluate(`getComputedStyle(document.querySelector('.social-shell')).getPropertyValue('--paper').trim().toUpperCase()`),'#070D1D',`${path}: midnight background`)
     if(width>=768) assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-navigation'),'::after').backgroundImage.includes('theme-refresh-v1/dark-dorado/sidebar-decoration.webp')`),true,`${path}: supplied midnight artwork`)
    } else if(theme==='bosque'&&!process.env.IDENTITY_BASELINE) {
     assert.equal(await evaluate(`getComputedStyle(document.querySelector('.social-shell')).getPropertyValue('--paper').trim().toUpperCase()`),'#073B2B',`${path}: forest background`)
     if(width>=768) assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-navigation'),'::after').backgroundImage.includes('theme-refresh-v1/bosque/sidebar-decoration.webp')`),true,`${path}: supplied forest artwork`)
    }
    if(path==='/'&&!process.env.IDENTITY_BASELINE) {
     const backgrounds=await evaluate(`(()=>{
      const split=value=>{let depth=0,start=0,items=[];for(let i=0;i<value.length;i++){if(value[i]==='(')depth++;if(value[i]===')')depth--;if(value[i]===','&&!depth){items.push(value.slice(start,i).trim());start=i+1}}items.push(value.slice(start).trim());return items};
      return [['.profile-starfield','::before'],['.sidebar-navigation','::after'],['.reader-summary',null],['.reader-summary','::before'],['.social-page-column','::after']].flatMap(([selector,pseudo])=>{const e=document.querySelector(selector);if(!e)return [];const s=getComputedStyle(e,pseudo),images=split(s.backgroundImage),sizes=split(s.backgroundSize);return images.flatMap((image,index)=>image.startsWith('url(')?[{selector,pseudo,image,size:sizes[index%sizes.length]}]:[])})
     })()`)
     for(const bg of backgrounds)assert.match(bg.size,/auto|cover|contain/,`${theme} ${width} ${bg.selector}${bg.pseudo||''} distorts image: ${bg.size}`)
    }
    if(theme==='rosa-antiguo'&&!process.env.IDENTITY_BASELINE) {
     assert.equal(await evaluate(`getComputedStyle(document.querySelector('.profile-starfield'),'::before').backgroundImage.includes('theme-refresh-v1/rosa-antiguo/banner.webp')`),true,`${path}: isolated cotton landscape`)
     assert.equal(await evaluate(`getComputedStyle(document.querySelector('.profile-starfield'),'::before').backgroundImage.includes('atlas')`),false,`${path}: no neighboring atlas pieces`)
    }
    if(await evaluate(`document.documentElement.dataset.themePack==='literary'`)) {
     const art=await evaluate(`(()=>{const e=document.querySelector('.profile-starfield');return {header:e?getComputedStyle(e,'::before').backgroundImage:'',sidebar:getComputedStyle(document.querySelector('.sidebar-navigation'),'::after').backgroundImage,corner:document.querySelector('.reader-summary')?getComputedStyle(document.querySelector('.reader-summary')).backgroundImage:''}})()`)
     const ready=await evaluate(`import('/src/theme/literaryThemes.js').then(m=>Boolean(m.literaryThemes.find(t=>t.id==='${theme}').art))`)
     if(ready) {
      assert.ok(art.header.includes('/images/themes/'+theme+'/banner.webp'),`${path}: own banner`)
      if(width>=701)assert.ok(art.sidebar.includes('/images/themes/'+theme+'/sidebar-decoration.webp'),`${path}: own sidebar`)
      if(path==='/')assert.ok(art.corner.includes('/images/themes/'+theme+'/corner.webp'),'own corner')
     } else {
      assert.ok(!art.header.includes('url(')&&!art.sidebar.includes('url(')&&!art.corner.includes('url('),`${theme}: pending art has no fabricated URLs`)
     }
    }
    if(theme==='dark-rosado'&&!process.env.IDENTITY_BASELINE) {
     assert.equal(await evaluate(`getComputedStyle(document.querySelector('.social-shell')).getPropertyValue('--paper').trim().toUpperCase()`),'#25151F',`${path}: rose palette`)
     if(width>=768)assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-navigation'),'::after').backgroundImage.includes('rose-universe/rose-books-sidebar-v2.png')`),true,`${path}: rose sidebar`)
     if(path==='/')assert.equal(await evaluate(`getComputedStyle(document.querySelector('.reader-summary')).backgroundImage.includes('rose-universe/lantern-corner-v1.png')`),true,'separate rose lantern panel')
    }
    if(theme==='invierno'&&!process.env.IDENTITY_BASELINE) {
     assert.equal(await evaluate(`getComputedStyle(document.querySelector('.social-shell')).getPropertyValue('--paper').trim().toUpperCase()`),'#D9EAF7',`${path}: crystal palette`)
     if(width>=768)assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-navigation'),'::after').backgroundImage.includes('theme-refresh-v1/invierno/sidebar-decoration.webp')`),true,`${path}: crystal sidebar`)
     if(path==='/')assert.equal(await evaluate(`getComputedStyle(document.querySelector('.reader-summary')).backgroundImage.includes('theme-refresh-v1/invierno/corner.webp')`),true,'separate crystal corner')
     if(path==='/'&&width>=701) {
      const panorama=await evaluate(`(()=>{const s=getComputedStyle(document.querySelector('.profile-starfield'),'::before');return {size:s.backgroundSize,ratio:s.aspectRatio}})()`)
      assert.equal(panorama.size,'auto, 100% auto',`${width}: panorama preserves image aspect ratio`)
      assert.equal(panorama.ratio,'3 / 1',`${width}: natural panorama proportions`)
     }
    }
    if(width===390&&path==='/') {
     const point=await evaluate(`(()=>{window.scrollTo(0,0);const e=document.querySelector('.mobile-nav-toggle'),r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`)
     await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point})
     await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point})
     await until(`document.querySelector('.mobile-nav-toggle').getAttribute('aria-expanded')==='true'`)
     assert.equal(await evaluate(`document.querySelector('.sidebar-navigation').getAttribute('aria-modal')`),'true')
     await evaluate(`document.querySelector('.mobile-drawer-heading button').click()`)
     await until(`document.querySelector('.mobile-nav-toggle').getAttribute('aria-expanded')==='false'`)
    }
    const identity = await evaluate(`(()=>{const e=document.querySelector('.literary-atmosphere');return e?{hidden:e.getAttribute('aria-hidden'),pointer:getComputedStyle(e).pointerEvents,animation:getComputedStyle(e).animationName}:null})()`)
    if(path.startsWith('/admin')) assert.equal(identity,null)
    else if(!process.env.IDENTITY_BASELINE&&theme==='dark-rosado') assert.equal(await evaluate(`getComputedStyle(document.querySelector('.literary-atmosphere')).display`),'none','original theme has no interior overlay')
    else if(!process.env.IDENTITY_BASELINE) assert.deepEqual(identity,{hidden:'true',pointer:'none',animation:'none'},`${theme} ${width} ${path}: static decoration`)
    if((width===1440||width===390||width===1920)&&(!process.env.CAPTURE_ONLY_MURAL||path==='/')){
     const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(new URL(`../../../artifacts/${captureFolder}/${theme}-${width}-${(path==='/'?'mural':path.replaceAll('/','').replaceAll('?','-').replaceAll('=','-'))}.png`,import.meta.url),Buffer.from(screenshot.result.data,'base64'))
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
 console.log(process.env.IDENTITY_BASELINE ? `PASS: baseline captures for ${selectedThemes.length} theme(s), nine app views and six viewport sizes` : `PASS: ${selectedThemes.length} theme(s), nine app views, seven viewport sizes, proportional artwork, text contrast >=4.5:1, control boundaries >=3:1; no runtime exceptions or horizontal overflow`)
}finally{socket.close();await browserCall('Target.disposeBrowserContext',{browserContextId});browser.close()}



