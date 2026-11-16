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
  await until(`Boolean(document.querySelector('.social-shell'))`)
  await evaluate(`history.pushState({},'','/');window.dispatchEvent(new PopStateEvent('popstate'))`)
  const themes=await evaluate(`import('/src/theme/themes.js').then(m=>m.themes.map(t=>t.id))`)
  await mkdir(new URL('../../../artifacts/footer-pieces-v2/',import.meta.url),{recursive:true})
  for(const width of [1920,1280,390]) {
    const height=width===390?844:1050
    await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false})
    for(const theme of themes) {
      await evaluate(`localStorage.setItem('libria_theme','${theme}');window.dispatchEvent(new StorageEvent('storage',{key:'libria_theme',newValue:'${theme}'}))`)
      await until(`document.documentElement.dataset.theme==='${theme}'`)
      const sample=await evaluate(`(async()=>{
        const assets=(await import('/src/theme/themeFooters.js')).getThemeFooterAssets('${theme}');
        const loaded=[];
        for(const [part,src] of Object.entries(assets)) {
          const image=new Image();image.src=src;await image.decode();
          const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
          const context=canvas.getContext('2d');context.drawImage(image,0,0);
          loaded.push({part,width:image.naturalWidth,alpha:context.getImageData(part==='strip'?Math.floor(canvas.width/2):0,0,1,1).data[3]});
        }
        const style=getComputedStyle(document.querySelector('.profile-starfield'),'::after');
        return {assets,loaded,image:style.backgroundImage,repeat:style.backgroundRepeat,size:style.backgroundSize,opacity:Number(style.opacity),filter:style.filter,pointer:style.pointerEvents,overflow:document.documentElement.scrollWidth>innerWidth+1};
      })()`)
      assert.notEqual(sample.assets.corner,sample.assets.strip,`${theme}: separate files`)
      assert.ok(sample.image.includes(sample.assets.corner)&&sample.image.includes(sample.assets.strip),`${theme}: both images visible`)
      assert.equal(sample.repeat,'no-repeat, repeat-x',`${theme}: only the strip repeats`)
      assert.equal(sample.size,width===390?'auto 180px, 720px 240px':'auto 360px, 960px 320px',`${theme}: independent proportional scale`)
      assert.equal(sample.opacity,width===390?.45:.55,`${theme}: subdued opacity`)
      assert.ok(sample.filter.includes('blur(0.6px)'),`${theme}: softened footer`)
      assert.equal(sample.pointer,'none',`${theme}: decorative only`)
      assert.ok(!sample.overflow,`${theme} ${width}: no horizontal overflow`)
      for(const asset of sample.loaded) {
        assert.ok(asset.width>=(asset.part==='strip'?900:600),`${theme} ${asset.part}: high resolution`)
        assert.ok(asset.alpha<24,`${theme} ${asset.part}: transparency preserved`)
      }
      if(width!==1280) {
        const shot=await send('Page.captureScreenshot',{format:'png',...(width===1920?{clip:{x:1500,y:630,width:420,height:420,scale:1}}:{})})
        await writeFile(new URL(`../../../artifacts/footer-pieces-v2/${theme}-${width}.png`,import.meta.url),Buffer.from(shot.data,'base64'))
      }
    }
    console.log(`${themes.length} themes at ${width}px: two images, alpha, resolution, softness and layout passed`)
  }
} finally {
  socket.close()
  await fetch(`${cdp}/json/close/${target.id}`)
}
