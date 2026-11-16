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
const {mkdir,writeFile}=await import('node:fs/promises')
try {
  await send('Page.navigate',{url:`${app}/tests/fixtures/theme-refinements.html?role=admin&scene=mural`})
  await until(`Boolean(document.querySelector('.reader-profile--panoramic'))`)
  await mkdir(new URL('../../../artifacts/profile-panorama/',import.meta.url),{recursive:true})
  const themes=await evaluate(`import('/src/theme/themes.js').then(m=>m.themes.map(t=>t.id))`)
  for(const width of [1920,390]) {
    await send('Emulation.setDeviceMetricsOverride',{width,height:width===1920?1050:900,deviceScaleFactor:1,mobile:false})
    for(const theme of width===1920 ? themes : ['dark-blood','dark','lavanda','canto-sirenas']) {
      await evaluate(`localStorage.setItem('libria_theme','${theme}');window.dispatchEvent(new StorageEvent('storage',{key:'libria_theme',newValue:'${theme}'}))`)
      await until(`document.documentElement.dataset.theme==='${theme}'`)
      const src=await evaluate(`import('/src/theme/profileBanners.js').then(m=>m.getProfileBanner('${theme}',true).src)`)
      await until(`document.querySelector('.reader-profile-cover img').getAttribute('src')===${JSON.stringify(src)}&&document.querySelector('.reader-profile-cover img').complete`)
      await evaluate(`document.querySelector('.reader-profile-cover img').decode()`)
      await new Promise(resolve=>setTimeout(resolve,120))
      const layout=await evaluate(`(()=>{
        const cover=document.querySelector('.reader-profile-cover--panoramic'),background=cover.getBoundingClientRect(),identity=document.querySelector('.reader-profile-identity').getBoundingClientRect(),page=document.querySelector('.reader-profile').getBoundingClientRect(),tabs=document.querySelector('.reader-profile-tabs').getBoundingClientRect(),aside=document.querySelector('.reader-personal-column').getBoundingClientRect(),about=document.querySelector('.reader-about-section').getBoundingClientRect();
        return {position:getComputedStyle(cover).position,radius:getComputedStyle(cover).borderRadius,full:background.left<=page.left+1&&background.right>=page.right-1,nameOnBackground:identity.top>=background.top&&identity.bottom<=background.bottom+1,asideBelowTabs:aside.top>=tabs.bottom-1,asideRight:aside.left>=about.right-1,counters:document.querySelectorAll('.profile-community-counter').length,actions:document.querySelectorAll('.profile-community-header .profile-community-actions button').length,overflow:document.documentElement.scrollWidth>innerWidth+1};
      })()`)
      assert.equal(layout.position,'absolute','Cover is a backdrop, not a separate banner')
      if(width===1920)assert.equal(await evaluate(`getComputedStyle(document.querySelector('.reader-profile-cover')).minHeight`),'360px','Panorama has enough height to show the scene')
      if(width===1920&&theme!=='dark-blood')assert.ok(await evaluate(`(()=>{const image=document.querySelector('.reader-profile-cover img');return Math.abs(image.clientWidth/image.clientHeight-image.naturalWidth/image.naturalHeight)<.02&&Math.abs(image.clientHeight-image.parentElement.clientHeight)<2})()`),'Scene keeps its natural proportions and fits the header height')
      assert.equal(layout.radius,'0px')
      assert.ok(layout.full&&layout.nameOnBackground,`${theme}: full header behind name`)
      assert.ok(layout.asideBelowTabs,`${theme}: challenge starts below profile navigation`)
      if(width===1920)assert.ok(layout.asideRight,`${theme}: personal cards stay beside About me`)
      if(width===1920)assert.ok(await evaluate(`Math.abs(document.querySelector('.reader-personal-column > :first-child').getBoundingClientRect().top-document.querySelector('.reader-story').getBoundingClientRect().top)<2`),`${theme}: reading challenge aligns with story`)
      assert.equal(layout.counters,5)
      assert.equal(layout.actions,3)
      assert.equal(await evaluate(`document.querySelector('.reader-about-title').textContent`),'Mi universo literario')
      assert.equal(await evaluate(`document.querySelector('.reader-profile-tabs button').textContent`),'Sobre mí','Navigation label stays unchanged')
      assert.ok(await evaluate(`Math.abs(document.querySelector('.reader-story').getBoundingClientRect().width-document.querySelector('.reader-about-grid').getBoundingClientRect().width)<2`),'Story spans the content column')
      await evaluate(`document.querySelector('.reader-story-decoration-slot')?.decode()`)
      assert.ok(!layout.overflow,`${theme} ${width}: no horizontal overflow`)
      const shot=await send('Page.captureScreenshot',{format:'png'})
      await writeFile(new URL(`../../../artifacts/profile-panorama/${theme}-${width}.png`,import.meta.url),Buffer.from(shot.data,'base64'))
    }
    console.log(`${width}px: panoramic header, name overlay, actions, and challenge placement passed in ${width===1920?themes.length:4} themes`)
  }
}finally{socket.close();await fetch(`${cdp}/json/close/${target.id}`)}
