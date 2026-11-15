import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
const cdp = process.env.CDP_URL || 'http://127.0.0.1:9224'
const app = 'http://127.0.0.1:5173'
const target = await (await fetch(`${cdp}/json/new?about:blank`, { method: 'PUT' })).json()
const socket = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
let sequence = 0
const pending = new Map()
socket.onmessage = event => { const data = JSON.parse(event.data); if (pending.has(data.id)) { pending.get(data.id)(data); pending.delete(data.id) } }
const send = (method, params = {}) => new Promise(resolve => { pending.set(++sequence, resolve); socket.send(JSON.stringify({ id: sequence, method, params })) })
async function evaluate(expression) { const value = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }); if (value.result?.exceptionDetails) throw Error(JSON.stringify(value.result.exceptionDetails)); return value.result.result.value }
async function until(expression) { for (let n=0;n<600;n++) { if(await evaluate(expression))return; await new Promise(r=>setTimeout(r,50)) } throw Error('Timed out: '+expression) }
try {
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'no-preference'}]})
  await send('Page.navigate', { url: `${app}/tests/fixtures/login-universe.html` })
  await until(`Boolean(document.querySelector('.login-card'))`)
  await mkdir(new URL('../../../artifacts/login-universe/',import.meta.url),{recursive:true})
  for (const [width,height] of [[1792,859],[1440,900],[1024,768],[768,1024],[1023,768],[390,844],[320,568],[844,390],[667,375],[390,450]]) {
    await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<768})
    await evaluate(`new Promise(resolve=>{scrollTo(0,0);requestAnimationFrame(()=>requestAnimationFrame(resolve))})`)
    const layout = await evaluate(`(()=>{const card=document.querySelector('.login-card').getBoundingClientRect();return {horizontal:document.documentElement.scrollWidth>innerWidth,top:card.top,left:card.left,right:card.right,forms:document.querySelectorAll('.login-card').length,font:parseFloat(getComputedStyle(document.querySelector('input')).fontSize),stars:[...document.querySelectorAll('.login-star')].filter(e=>getComputedStyle(e).display!=='none').length}})()`)
    assert.equal(layout.horizontal,false,`${width}x${height} overflow`)
    assert.ok(layout.top>=0 && layout.left>=0 && layout.right<=width,`${width}x${height}: ${JSON.stringify(layout)}`)
    assert.equal(layout.forms,1); assert.ok(layout.font>=16)
    assert.equal(layout.stars,width<768?48:width<1024?80:120)
    if ((width===1792 && height===859) || (width===390 && height===844)) {
      const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})
      await writeFile(new URL(`../../../artifacts/login-universe/${process.env.BROWSER_NAME || 'chrome'}-${width}.png`,import.meta.url),Buffer.from(screenshot.result.data,'base64'))
    }
    await evaluate(`document.querySelector('.login-card a:last-child').scrollIntoView({block:'end'})`)
  }
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
  await evaluate(`scrollTo(0,0)`)
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.login-star')).animationName`),'login-twinkle')
  const brightness = await evaluate(`(async()=>{const samples=()=>[...document.querySelectorAll('.login-star,.login-lucero')].map(e=>Number(getComputedStyle(e).opacity));const before=samples();await new Promise(r=>setTimeout(r,900));const after=samples();return {stars:before.slice(0,120).some((v,i)=>Math.abs(v-after[i])>.1),luceros:before.slice(120).some((v,i)=>Math.abs(v-after[i+120])>.05)}})()`)
  assert.equal(brightness.stars,true,'Stars visibly change brightness')
  assert.equal(brightness.luceros,true,'Luceros visibly change brightness')
  assert.equal(await evaluate(`Boolean(document.querySelector('.google-login svg path[fill="#4285F4"]'))`),true)

  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]})
  assert.equal(await evaluate(`document.querySelector('.login-page').dataset.motion`),'enabled','Effects stay enabled until the user pauses them')
  await evaluate(`document.querySelector('.login-motion-toggle').click()`)
  await until(`document.querySelector('.login-page').dataset.motion==='disabled'`)
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.login-star')).animationName`),'none')
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.login-shooting-star')).display`),'none')
  await evaluate(`document.querySelector('.login-motion-toggle').click()`)
  await until(`getComputedStyle(document.querySelector('.login-star')).animationName==='login-twinkle'`)
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.login-shooting-star')).display`),'block','Explicit opt-in allows effects with reduced motion enabled')
  await evaluate(`document.querySelector('.login-motion-toggle').click()`)
  await until(`getComputedStyle(document.querySelector('.login-star')).animationName==='none'`)
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'no-preference'}]})
  await evaluate(`document.querySelector('.login-motion-toggle').click()`)
  await until(`document.querySelector('.login-page').dataset.motion==='enabled'`)
  assert.equal(await evaluate(`document.querySelector('.login-universe').getAttribute('aria-hidden')`),'true')
  await until(`document.querySelector('.login-shooting-star').getAnimations().some(a=>a.playState==='running')`)
  assert.equal(await evaluate(`document.querySelector('.login-shooting-star').getAnimations().filter(a=>a.playState==='running').length`),1)
  assert.equal(await evaluate(`document.querySelector('.login-universe').contains(document.querySelector('.login-shooting-star')) && Number(getComputedStyle(document.querySelector('.login-universe')).zIndex)<Number(getComputedStyle(document.querySelector('.login-card')).zIndex)`),true,'Shooting star stays behind form')
  await evaluate(`(()=>{for(const [name,value] of [['email','reader@example.com'],['password','testpassword']]){const e=document.querySelector('[name='+name+']');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,value);e.dispatchEvent(new Event('input',{bubbles:true}))}})()`)
  await evaluate(`document.querySelector('[aria-label="Mostrar contraseña"]').click()`)
  assert.equal(await evaluate(`document.querySelector('[name=password]').type`),'text')
  assert.equal(await evaluate(`document.querySelector('[name=password]').value`),'testpassword')
  await evaluate(`document.querySelector('.login-card').requestSubmit()`)
  await until(`Boolean(document.querySelector('.form-error'))`)
  assert.deepEqual(await evaluate(`window.loginTest.calls.find(c=>c.path.endsWith('/auth/login')).body`),{email:'reader@example.com',password:'testpassword'})
  assert.equal(await evaluate(`document.querySelector('a.google-login').pathname.endsWith('/auth/google/login')`),true)
  assert.equal(await evaluate(`Boolean(document.querySelector('a[href="/recover-account"]'))`),true)
  assert.equal(await evaluate(`Boolean(document.querySelector('a[href="/register"]'))`),true)
  await mkdir(new URL('../../../artifacts/login-universe/',import.meta.url),{recursive:true})
  const shot=await send('Page.captureScreenshot',{format:'png'})
  await writeFile(new URL(`../../../artifacts/login-universe/${process.env.BROWSER_NAME || 'chrome'}.png`,import.meta.url),Buffer.from(shot.result.data,'base64'))
  console.log('PASS: 10 responsive sizes, scroll access, input font size, star density, reduced motion, password visibility, login payload and preserved auth links')
} finally { socket.close(); await fetch(`${cdp}/json/close/${target.id}`) }
