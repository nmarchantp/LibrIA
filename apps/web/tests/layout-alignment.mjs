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
const paths=['/','/profile','/profiles/fixture','/profile?tab=library','/books','/reading/book-fixture','/events','/recommendations','/messages','/notifications','/settings','/admin/profiles']
try {
  await send('Page.navigate',{url:`${app}/tests/fixtures/theme-refinements.html?role=admin&scene=mural`})
  await until(`Boolean(document.querySelector('.reader-profile'))`)
  for(const width of [1920,1440,1024,390]) {
    await send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false})
    for(const path of paths) {
      await evaluate(`history.pushState({},'',${JSON.stringify(path)});window.dispatchEvent(new PopStateEvent('popstate'))`)
      await until(`Boolean(document.querySelector('.social-main > :is(.page-width,.mural-layout)'))`)
      await new Promise(resolve=>setTimeout(resolve,100))
      const metrics=await evaluate(`(()=>{
        const main=document.querySelector('.social-main'), page=main.querySelector(':scope > :is(.page-width,.mural-layout)');
        const rect=page.getBoundingClientRect(),parent=main.getBoundingClientRect(),header=document.querySelector('.social-topbar').getBoundingClientRect();
        return {left:rect.left-parent.left,right:rect.right,rightGutter:parent.right-rect.right,top:Number.parseFloat(getComputedStyle(page).paddingTop)*Number(getComputedStyle(document.documentElement).zoom),expectedTop:Number.parseFloat(getComputedStyle(page).getPropertyValue('--main-top-space'))*Number(getComputedStyle(document.documentElement).zoom),width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth+1,zoom:getComputedStyle(document.documentElement).zoom};
      })()`)
      assert.ok(!metrics.overflow,`${width} ${path}: horizontal overflow`)
      assert.ok(metrics.right<=metrics.width+1,`${width} ${path}: right edge outside viewport`)
      if(width>=1000) {
        assert.ok(Math.abs(metrics.left-25.2)<1,`${width} ${path}: left gutter ${metrics.left}`)
        assert.ok(Math.abs(metrics.rightGutter-18)<1,`${width} ${path}: right gutter ${metrics.rightGutter}`)
        assert.ok(Math.abs(metrics.top-metrics.expectedTop)<1,`${width} ${path}: top spacing ${metrics.top}`)
      } else assert.equal(Number(metrics.zoom),1,`${path}: mobile scale`)
    }
    console.log(`${width}px: ${paths.length} routes aligned, no horizontal overflow`)
  }
  await send('Emulation.setDeviceMetricsOverride',{width:1920,height:1000,deviceScaleFactor:1,mobile:false})
  await evaluate(`localStorage.removeItem('libria_sidebar_collapsed')`)
  await send('Page.navigate',{url:`${app}/tests/fixtures/theme-refinements.html?role=admin&scene=mural`})
  await until(`Boolean(document.querySelector('.sidebar-collapse-toggle'))`)
  const expandedWidth=await evaluate(`document.querySelector('.social-sidebar').getBoundingClientRect().width`)
  await evaluate(`document.querySelector('.sidebar-collapse-toggle').click()`)
  await until(`document.querySelector('.sidebar-collapse-toggle').getAttribute('aria-expanded')==='false'`)
  assert.equal(await evaluate(`localStorage.getItem('libria_sidebar_collapsed')`),'true')
  assert.ok(await evaluate(`document.querySelector('.social-sidebar').getBoundingClientRect().width < ${expandedWidth}/2`),'Collapsed sidebar frees horizontal space')
  assert.equal(await evaluate(`document.querySelector('.social-nav a').title`),'Mural')
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-navigation'),'::after').display`),'none')
  await send('Page.navigate',{url:`${app}/tests/fixtures/theme-refinements.html?role=admin&scene=mural`})
  await until(`Boolean(document.querySelector('.sidebar-collapsed'))`)
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:1000,deviceScaleFactor:1,mobile:false})
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-collapse-toggle')).display`),'none')
  await evaluate(`document.querySelector('.mobile-nav-toggle').click()`)
  await until(`document.querySelector('.sidebar-navigation').getAttribute('aria-modal')==='true'`)
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.social-nav a > span')).position`),'static','Mobile labels remain visible')
  await evaluate(`document.querySelector('.mobile-drawer-heading button').click()`)
  await send('Emulation.setDeviceMetricsOverride',{width:1920,height:1000,deviceScaleFactor:1,mobile:false})
  await evaluate(`document.querySelector('.sidebar-collapse-toggle').click()`)
  await until(`!document.querySelector('.sidebar-collapsed')`)
  assert.equal(await evaluate(`localStorage.getItem('libria_sidebar_collapsed')`),'false')
  console.log('Sidebar: collapse, expand, persistence, and mobile drawer passed')
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'no-preference'}]})
  await evaluate(`for(const key of ['libriaverse-magical-background','libriaverse-magical-background-motion']) { localStorage.setItem(key,'true');window.dispatchEvent(new StorageEvent('storage',{key,newValue:'true'})) }`)
  await until(`document.querySelector('.social-page-column').dataset.starfieldMotion==='enabled'`)
  const themes=await evaluate(`import('/src/theme/themes.js').then(m=>m.themes.map(t=>t.id))`)
  const exposedCandles={'arenas-destino':1,'olimpo-eterno':1,'dark-dorado':1,'oraculo-luna':3,'catedral-cristal':3,'ecos-sombras':3,'aquelarre-medianoche':2}
  for(const theme of themes) {
    await evaluate(`localStorage.setItem('libria_theme',${JSON.stringify(theme)});window.dispatchEvent(new StorageEvent('storage',{key:'libria_theme',newValue:${JSON.stringify(theme)}}))`)
    await until(`document.documentElement.dataset.theme===${JSON.stringify(theme)}`)
    const icons=await evaluate(`[...document.querySelectorAll('.global-header-action > svg')].map(e=>{const s=getComputedStyle(e);return {width:s.width,height:s.height,fill:s.fill,stroke:s.stroke,color:s.color,weight:s.strokeWidth,outlined:[...e.querySelectorAll('path,rect,circle,line,polyline,polygon,ellipse')].every(p=>getComputedStyle(p).fill==='none'&&getComputedStyle(p).strokeWidth==='1.75px')}})`)
    assert.equal(icons.length,4,`${theme}: four shared header icons`)
    for(const icon of icons) {
      assert.ok(Math.abs(Number.parseFloat(icon.width)-22)<.05,`${theme}: uniform icon width`)
      assert.ok(Math.abs(Number.parseFloat(icon.height)-22)<.05,`${theme}: uniform icon height`)
      assert.equal(icon.fill,'none',`${theme}: outlined icon`)
      assert.equal(icon.weight,'1.75px',`${theme}: uniform stroke`)
      assert.equal(icon.stroke,icon.color,`${theme}: inherits theme color`)
      assert.ok(icon.outlined,`${theme}: no filled shapes`)
    }
    if(theme==='dark'||theme==='lavanda') {
      await evaluate(`history.pushState({},'','/');window.dispatchEvent(new PopStateEvent('popstate'))`)
      await until(`Boolean(document.querySelector('.mural-heading'))`)
      const logo=await evaluate(`(()=>{const e=document.querySelector('.social-sidebar > .brand-link');return {background:getComputedStyle(e).backgroundImage,before:getComputedStyle(e,'::before').content,after:getComputedStyle(e,'::after').content,sidebar:getComputedStyle(document.querySelector('.social-sidebar')).backgroundImage}})()`)
      assert.deepEqual(logo,{background:'none',before:'none',after:'none',sidebar:'none'},`${theme}: mural logo and sidebar stay free of decorative backgrounds`)
      await evaluate(`history.pushState({},'','/profile');window.dispatchEvent(new PopStateEvent('popstate'))`)
      await until(`Boolean(document.querySelector('.reader-profile'))`)
    }
    if(theme==='dark-blood') {
      assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-candle-flame-shape')).animationName`),'blood-flame-breathe')
    } else {
      assert.equal(await evaluate(`document.querySelectorAll('.artwork-candle').length`),exposedCandles[theme] || 0,`${theme}: only designated exposed flames animate`)
      assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-artwork-light')).animationName`),theme==='archivo-galactico' ? 'none' : 'sidebar-light-flicker',theme)
      if(theme==='archivo-galactico') {
        await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:1000,y:5})
        assert.equal(await evaluate(`getComputedStyle(document.querySelector('.artwork-lamp-illumination')).animationName`),'none','Lamp beam is steady at rest')
        const hit=await evaluate(`(()=>{const r=document.querySelector('.artwork-lamp-hit').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`)
        for(let pass=0;pass<2;pass++) {
          await send('Input.dispatchMouseEvent',{type:'mouseMoved',...hit})
          await until(`getComputedStyle(document.querySelector('.artwork-lamp-illumination')).animationName==='artwork-lamp-intermittent'`)
          assert.equal(await evaluate(`getComputedStyle(document.querySelector('.artwork-lamp-illumination')).animationIterationCount`),'1','Single burst on each mouse entry')
          const values=await evaluate(`new Promise(resolve=>{const e=document.querySelector('.artwork-lamp-illumination'),a=[];let n=0;const sample=()=>{a.push(getComputedStyle(e).opacity);if(++n<12)setTimeout(sample,55);else resolve(a)};sample()})`)
          assert.ok(new Set(values).size>2,'Lamp beam visibly changes brightness')
          await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:1000,y:5})
          await until(`getComputedStyle(document.querySelector('.artwork-lamp-illumination')).animationName==='none'`)
        }
      }
      assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-artwork-canvas image')).transform`),'none',`${theme}: image remains still`)
      assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-artwork-canvas')).animationName`),'none',`${theme}: canvas remains still`)
      if(await evaluate(`Boolean(document.querySelector('.artwork-candle'))`)) {
        const hit=await evaluate(`(()=>{const r=document.querySelector('.artwork-candle-hit').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`)
        await send('Input.dispatchMouseEvent',{type:'mouseMoved',...hit})
        await until(`getComputedStyle(document.querySelector('.artwork-candle-flame')).animationName==='blood-flame-gust'`)
        assert.equal(await evaluate(`getComputedStyle(document.querySelector('.artwork-candle-halo')).animationName`),'artwork-halo-gust',`${theme}: halo reacts with flame`)
        assert.equal(await evaluate(`getComputedStyle(document.querySelector('.artwork-candle-halo')).animationDelay`),await evaluate(`getComputedStyle(document.querySelector('.artwork-candle-flame')).animationDelay`),`${theme}: flame and halo synchronized`)
        await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:1000,y:5})
      }
    }
  }
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]})
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-artwork-light')).animationName`),'sidebar-light-flicker','Light is independent of background motion')
  await send('Emulation.setEmulatedMedia',{features:[]})
  await evaluate(`localStorage.setItem('libriaverse-magical-background-motion','false');window.dispatchEvent(new StorageEvent('storage',{key:'libriaverse-magical-background-motion',newValue:'false'}))`)
  await until(`document.querySelector('.social-page-column').dataset.starfieldMotion==='disabled'`)
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-artwork-light')).animationName`),'sidebar-light-flicker','Background motion toggle does not stop sidebar light')
  const firstOpacity=await evaluate(`getComputedStyle(document.querySelector('.sidebar-artwork-light')).opacity`)
  await new Promise(resolve=>setTimeout(resolve,350))
  assert.notEqual(await evaluate(`getComputedStyle(document.querySelector('.sidebar-artwork-light')).opacity`),firstOpacity,'Only the light flickers over time')
  await evaluate(`localStorage.setItem('libriaverse-magical-background-motion','true');window.dispatchEvent(new StorageEvent('storage',{key:'libriaverse-magical-background-motion',newValue:'true'}));localStorage.setItem('libria_theme','dark-blood');window.dispatchEvent(new StorageEvent('storage',{key:'libria_theme',newValue:'dark-blood'}))`)
  await until(`Boolean(document.querySelector('.sidebar-candle-reactor[data-animated="true"]'))`)
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]})
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.sidebar-candle-flame-shape')).animationName`),'blood-flame-breathe','Original candle remains animated')
  for(const height of [1000,900,768]) {
    await send('Emulation.setDeviceMetricsOverride',{width:1920,height,deviceScaleFactor:1,mobile:false})
    const bounds=await evaluate(`(()=>{
      const nav=document.querySelector('.social-nav').getBoundingClientRect();
      const art=document.querySelector('.sidebar-candle-reactor').getBoundingClientRect();
      const account=document.querySelector('.sidebar-account').getBoundingClientRect();
      const sidebar=document.querySelector('.social-sidebar').getBoundingClientRect();
      return {navBottom:nav.bottom,artTop:art.top,accountBottom:account.bottom,sidebarBottom:sidebar.bottom};
    })()`)
    assert.ok(bounds.artTop>=bounds.navBottom-1,`${height}px: candle must remain below navigation`)
    assert.ok(bounds.sidebarBottom-bounds.accountBottom<30,`${height}px: account stays at sidebar bottom`)
  }
  const hit=await evaluate(`(()=>{const r=document.querySelector('.sidebar-candle-hit').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`)
  await send('Input.dispatchMouseEvent',{type:'mouseMoved',...hit})
  await until(`getComputedStyle(document.querySelector('.sidebar-candle-flame-shape')).animationName==='blood-flame-gust'`)
  console.log(`${themes.length} themes: static images, localized light flicker, and candle mouse interaction passed`)
} finally {
  socket.close()
  await fetch(`${cdp}/json/close/${target.id}`)
}
