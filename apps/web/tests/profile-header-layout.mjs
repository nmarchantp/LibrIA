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
  await send('Page.navigate',{url:`${app}/tests/fixtures/profile-social.html`})
  await until(`document.querySelector('.profile-community-counter strong')?.textContent==='7'`)
  await mkdir(new URL('../../../artifacts/profile-header-inline/',import.meta.url),{recursive:true})
  for(const width of [1440,390]) {
    await send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false})
    await new Promise(resolve=>setTimeout(resolve,100))
    const layout=await evaluate(`(()=>{
      const title=document.querySelector('.reader-profile-title-row'),name=title.querySelector('h1').getBoundingClientRect(),stats=title.querySelector('.profile-community-counters').getBoundingClientRect();
      return {count:document.querySelectorAll('.reader-profile-identity').length,beside:stats.left>=name.right-1,values:[...title.querySelectorAll('strong')].map(n=>n.textContent),plain:[...title.querySelectorAll('.profile-community-counter')].every(n=>{const s=getComputedStyle(n);return s.borderTopWidth==='0px'&&s.boxShadow==='none'&&s.backgroundColor==='rgba(0, 0, 0, 0)'}),overflow:document.documentElement.scrollWidth>innerWidth+1,library:title.querySelector('a').getAttribute('href')};
    })()`)
    assert.equal(layout.count,1,'Single profile header')
    assert.deepEqual(layout.values,['7','2','3'],'Original statistics preserved')
    assert.ok(layout.plain,'Statistics have no cards, borders, or backgrounds')
    assert.ok(!layout.overflow,`${width}: no horizontal overflow`)
    assert.equal(layout.library,'/profile?tab=library')
    assert.ok(await evaluate(`(()=>{const stats=document.querySelector('.profile-community-counters').getBoundingClientRect(),actions=document.querySelector('.profile-community-actions').getBoundingClientRect();return actions.top>=stats.bottom-1&&Boolean(document.querySelector('.profile-community-header .profile-community-actions'))})()`),'Profile actions sit immediately below the counters')
    if(width===1440)assert.ok(layout.beside,'Statistics sit beside the name')
    const shot=await send('Page.captureScreenshot',{format:'png'})
    await writeFile(new URL(`../../../artifacts/profile-header-inline/${width}.png`,import.meta.url),Buffer.from(shot.data,'base64'))
    for(const [index,label] of [[1,'Seguidores'],[2,'Seguidos']]) {
      await evaluate(`document.querySelectorAll('.profile-community-counter')[${index}].click()`)
      await until(`Boolean(document.querySelector('dialog[open] .profile-person-link'))`)
      assert.ok(await evaluate(`document.querySelector('dialog[open]').textContent.includes('${label}')`))
      await evaluate(`document.querySelector('dialog[open] .reader-modal-close').click()`)
      await until(`!document.querySelector('dialog[open]')`)
    }
    for(const [index,title] of [[0,'Privacidad de mi perfil'],[1,'Comparte tu historia'],[2,'Descubrir personas']]) {
      await evaluate(`document.querySelectorAll('.profile-community-actions button')[${index}].click()`)
      await until(`Boolean(document.querySelector('dialog[open]'))`)
      assert.ok(await evaluate(`document.querySelector('dialog[open]').textContent.includes(${JSON.stringify(title)})`),'Profile action opens its original dialog')
      await evaluate(`document.querySelector('dialog[open] .reader-modal-close').click()`)
      await until(`!document.querySelector('dialog[open]')`)
    }
    console.log(`${width}px: inline counts, plain styles, library link, and connection lists passed`)
  }
  await evaluate(`window.socialTest.following=4;window.dispatchEvent(new Event('libria:book-activity-changed'))`)
  await until(`document.querySelectorAll('.profile-community-counter strong')[2].textContent==='4'`)
  console.log('Live statistics refresh preserved')
} finally {socket.close();await fetch(`${cdp}/json/close/${target.id}`)}
