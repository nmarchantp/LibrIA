import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { mkdir,writeFile } from 'node:fs/promises'
const cdp='http://127.0.0.1:9224',app='http://127.0.0.1:5173'
const target=await(await fetch(`${cdp}/json/new?about:blank`,{method:'PUT'})).json()
const ws=new WebSocket(target.webSocketDebuggerUrl)
await new Promise(resolve=>{ws.onopen=resolve})
let sequence=0
const pending=new Map(),errors=[]
ws.onmessage=event=>{const message=JSON.parse(event.data);if(message.method==='Runtime.exceptionThrown')errors.push(message.params);if(pending.has(message.id)){pending.get(message.id)(message);pending.delete(message.id)}}
const send=(method,params={})=>new Promise(resolve=>{pending.set(++sequence,resolve);ws.send(JSON.stringify({id:sequence,method,params}))})
async function evaluate(expression){const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.error||result.result?.exceptionDetails)throw Error(JSON.stringify(result));return result.result.result.value}
async function until(expression){for(let i=0;i<120;i++){if(await evaluate(expression))return;await new Promise(resolve=>setTimeout(resolve,50))}throw Error(`Timed out: ${expression}`)}
async function input(selector,value){await evaluate(`(()=>{const input=document.querySelector('${selector}');Object.getOwnPropertyDescriptor(input.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(value)});input.dispatchEvent(new Event('input',{bubbles:true}))})()`)}
try{
  await send('Runtime.enable')
  await send('Page.navigate',{url:`${app}/tests/fixtures/mural.html?count=6&role=admin`})
  await until(`Boolean(document.querySelector('.publication-create-shortcut'))`)
  assert.equal(await evaluate(`document.querySelectorAll('.mural-feed .post-composer,.mural-feed textarea').length`),0)
  const height=await evaluate(`document.querySelector('.publication-create-shortcut').getBoundingClientRect().height`)
  assert.ok(height>=44&&height<=70,`Compact launcher: ${height}`)
  for(let index=0;index<4;index++){
    await evaluate(`document.querySelector('.publication-create-shortcut').click()`)
    await until(`Boolean(document.querySelector('.content-management-dialog .post-composer'))`)
    await evaluate(`document.querySelectorAll('.post-composer .composer-types button')[${index}].click()`)
    await until(`document.querySelectorAll('.post-composer .composer-types button')[${index}].getAttribute('aria-pressed')==='true'`)
    assert.equal(await evaluate(`Boolean(document.querySelector('.composer-event-fields'))`),index===1)
    await evaluate(`document.querySelector('[aria-label="Cerrar edición"]').click()`)
    if(index>0){await until(`Boolean(document.querySelector('.composer-discard-confirm'))`);await evaluate(`document.querySelector('.composer-discard-confirm button:last-child').click()`)}
    await until(`!document.querySelector('.content-management-dialog')`)
  }
  assert.equal(await evaluate(`window.muralTest.requests.filter(request=>['POST','PUT','DELETE'].includes(request.method)).length`),0,'Opening must never save')
  await evaluate(`document.querySelector('.publication-create-shortcut').click()`)
  await until(`Boolean(document.querySelector('.post-composer'))`)
  await input('.composer-editor textarea','Un texto que no se debe perder')
  const document=await send('DOM.getDocument')
  const file=await send('DOM.querySelector',{nodeId:document.result.root.nodeId,selector:'.composer-photo-column input[multiple]'})
  await send('DOM.setFileInputFiles',{nodeId:file.result.nodeId,files:[fileURLToPath(new URL('../public/images/story-books-coffee.png',import.meta.url))]})
  await until(`document.querySelectorAll('.composer-thumbs img').length===1`)
  await evaluate(`document.querySelector('.content-management-dialog').dispatchEvent(new Event('cancel',{cancelable:true}))`)
  await until(`Boolean(document.querySelector('.composer-discard-confirm'))`)
  await evaluate(`document.querySelector('.composer-discard-confirm button').click()`)
  await until(`!document.querySelector('.composer-discard-confirm')`)
  assert.equal(await evaluate(`document.querySelector('.composer-editor textarea').value`),'Un texto que no se debe perder')
  assert.equal(await evaluate(`document.querySelectorAll('.composer-thumbs img').length`),1)
  const out=new URL('../../../artifacts/publication-composer/',import.meta.url);await mkdir(out,{recursive:true})
  for(const theme of ['lavanda','otono','invierno','bosque','rosa-antiguo','dark','dark-rosado','dark-blood','dark-dorado']){
    await evaluate(`import('/src/theme/themes.js').then(module=>module.applyTheme('${theme}'))`)
    for(const width of [1440,768,390,320]){
      await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<500})
      const geometry=await evaluate(`(()=>{const modal=document.querySelector('.content-management-dialog'),rect=modal.getBoundingClientRect();return {scroll:modal.scrollWidth,client:modal.clientWidth,width:rect.width,height:rect.height,viewport:innerWidth}})()`)
      assert.ok(geometry.scroll<=geometry.client+1&&geometry.width<=geometry.viewport&&geometry.height<=900,`${theme}/${width}: ${JSON.stringify(geometry)}`)
      await evaluate(`document.querySelector('.content-management-dialog').scrollTop=10000`)
      const footer=await evaluate(`document.querySelector('.composer-footer').getBoundingClientRect().toJSON()`)
      assert.ok(footer.bottom<=900&&footer.top>=0&&footer.height<=120,`${theme}/${width}: compact footer ${JSON.stringify(footer)}`)
      if(theme==='dark-dorado'&&[1440,390].includes(width)){const screenshot=await send('Page.captureScreenshot',{format:'png'});await writeFile(new URL(`composer-${width}.png`,out),Buffer.from(screenshot.result.data,'base64'))}
    }
  }
  await evaluate(`document.querySelector('.composer-footer button[type=button]').click()`)
  await until(`Boolean(document.querySelector('.composer-discard-confirm'))`)
  await evaluate(`document.querySelector('.composer-discard-confirm button:last-child').click()`)
  await until(`!document.querySelector('.content-management-dialog')`)
  await evaluate(`document.querySelector('.publication-create-shortcut').click()`)
  await until(`Boolean(document.querySelector('.post-composer'))`)
  await evaluate(`document.querySelectorAll('.post-composer .composer-types button')[1].click()`)
  await until(`Boolean(document.querySelector('[name="event_start_date"]'))`)
  await input('.composer-title','Nuevo encuentro de prueba')
  await input('.composer-editor textarea','Evento creado desde el compositor compacto')
  for(const [name,value] of Object.entries({event_start_date:'2026-11-14',event_start_time:'18:00',event_location:'Santiago',event_organizer:'LibrIAverse'}))await input(`[name="${name}"]`,value)
  await evaluate(`document.querySelector('.post-composer').requestSubmit();document.querySelector('.post-composer').requestSubmit()`)
  await until(`!document.querySelector('.content-management-dialog')`)
  assert.equal(await evaluate(`window.muralTest.requests.filter(request=>request.path==='/api/posts'&&request.method==='POST').length`),1)
  assert.equal(await evaluate(`window.muralTest.createdPublication.event_details.start_date`),'2026-11-14')
  await evaluate(`document.querySelector('a[href="/events"]').click()`)
  await until(`Array.from(document.querySelectorAll('.event-card')).some(card=>card.textContent.includes('Nuevo encuentro de prueba'))`)
  assert.deepEqual(errors,[])
  console.log('PASS: compact launcher, four categories, no save on open, dirty-close confirmation preserves text and photos, nine themes and accessible responsive footer')
}finally{ws.close();await fetch(`${cdp}/json/close/${target.id}`)}
