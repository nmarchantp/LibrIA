import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { mkdir, writeFile } from 'node:fs/promises'
const cdp='http://127.0.0.1:9224',app='http://127.0.0.1:5173'
const target=await(await fetch(`${cdp}/json/new?about:blank`,{method:'PUT'})).json()
const ws=new WebSocket(target.webSocketDebuggerUrl)
await new Promise(resolve=>{ws.onopen=resolve})
let sequence=0
const pending=new Map(),errors=[]
ws.onmessage=event=>{const message=JSON.parse(event.data);if(message.method==='Fetch.requestPaused')send('Fetch.fulfillRequest',{requestId:message.params.requestId,responseCode:200,responseHeaders:[{name:'Content-Type',value:'image/png'}],body:readFileSync(new URL('../public/images/story-books-cat.png',import.meta.url)).toString('base64')});if(message.method==='Runtime.exceptionThrown')errors.push(message.params);if(pending.has(message.id)){pending.get(message.id)(message);pending.delete(message.id)}}
const send=(method,params={})=>new Promise(resolve=>{pending.set(++sequence,resolve);ws.send(JSON.stringify({id:sequence,method,params}))})
async function evaluate(expression){const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.error||result.result?.exceptionDetails)throw Error(JSON.stringify(result));return result.result.result.value}
async function until(expression){for(let i=0;i<160;i++){if(await evaluate(expression))return;await new Promise(resolve=>setTimeout(resolve,50))}throw Error(`Timed out: ${expression}`)}
try{
  await send('Fetch.enable',{patterns:[{urlPattern:'*/api/posts/events-0/book-cover*',requestStage:'Request'}]})
  await send('Runtime.enable')
  await send('Emulation.setDeviceMetricsOverride',{width:1760,height:1100,deviceScaleFactor:1,mobile:false})
  await send('Page.navigate',{url:`${app}/tests/fixtures/mural.html?count=8&agenda=1&role=admin`})
  await until(`Boolean(document.querySelector('a[href="/events"]'))`)
  await evaluate(`history.pushState({},'', '/profile?tab=events');dispatchEvent(new PopStateEvent('popstate'))`)
  await until(`Boolean(document.querySelector('.personal-event-card'))`)
  assert.equal(await evaluate(`document.querySelectorAll('.reader-profile-tabs button').length`),5)
  assert.equal(await evaluate(`document.querySelector('.personal-events-privacy select').value`),'private')
  assert.equal(await evaluate(`document.querySelectorAll('.personal-event-card').length`),1)
  await evaluate(`fetch('http://127.0.0.1:8000/api/events/events-1/attendance',{method:'PUT'}).then(()=>dispatchEvent(new Event('libria-event-attendance-updated')))`)
  await until(`document.querySelectorAll('.personal-event-card').length===2`)
  await until(`document.querySelector('.personal-event-image img')?.naturalWidth>0`)
  assert.equal(await evaluate(`(()=>{const cards=[...document.querySelectorAll('.personal-event-card')].map(node=>node.getBoundingClientRect());return Math.abs(cards[0].top-cards[1].top)<1&&Math.abs(cards[0].height-cards[1].height)<1})()`),true)
  await evaluate(`import('/src/theme/themes.js').then(module=>module.applyTheme('dark-dorado'));document.querySelector('.personal-events').scrollIntoView({block:'start',behavior:'instant'})`)
  await evaluate(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`)
  assert.equal(await evaluate(`[...document.querySelectorAll('.personal-event-image img')].every(image=>image.getBoundingClientRect().height>100)`),true,'Event images have a visible vertical area')
  await mkdir(new URL('../../../artifacts/profile-events/',import.meta.url),{recursive:true})
  const screenshot=await send('Page.captureScreenshot',{format:'png'})
  await writeFile(new URL('../../../artifacts/profile-events/desktop.png',import.meta.url),Buffer.from(screenshot.result.data,'base64'))
  const themes=['lavanda','otono','invierno','rosa-antiguo','bosque','dark','dark-rosado','dark-blood','dark-dorado']
  for(const width of [1760,1024,390]){
    await send('Emulation.setDeviceMetricsOverride',{width,height:1100,deviceScaleFactor:1,mobile:width<500})
    for(const theme of themes){
      await evaluate(`import('/src/theme/themes.js').then(module=>module.applyTheme(${JSON.stringify(theme)}))`)
      assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth+1`),true,`${width} ${theme}: no overflow`)
      assert.equal(await evaluate(`(()=>{const card=document.querySelector('.personal-event-card').getBoundingClientRect();return card.width>250&&card.height<650})()`),true)
    }
  }
  await evaluate(`fetch('http://127.0.0.1:8000/api/events/events-1/attendance',{method:'DELETE'}).then(()=>dispatchEvent(new Event('libria-event-attendance-updated')))`)
  await until(`document.querySelectorAll('.personal-event-card').length===1`)
  await evaluate(`(()=>{const select=document.querySelector('.personal-events-privacy select');Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(select,'public');select.dispatchEvent(new Event('change',{bubbles:true}))})()`)
  await until(`document.querySelector('.personal-events-privacy select').value==='public'&&!document.querySelector('.personal-events-privacy select').disabled`)
  await evaluate(`history.pushState({},'', '/profiles/visitor?tab=events');dispatchEvent(new PopStateEvent('popstate'))`)
  await until(`Boolean(document.querySelector('.personal-event-card'))`)
  assert.equal(await evaluate(`document.querySelector('.personal-events-privacy')`),null)
  assert.equal(await evaluate(`document.querySelector('.personal-event-actions button')`),null)
  await evaluate(`history.pushState({},'', '/events');dispatchEvent(new PopStateEvent('popstate'))`)
  await until(`Boolean(document.querySelector('.agenda-upcoming [data-event-id="events-0"]'))`)
  await evaluate(`document.querySelector('.agenda-upcoming [data-event-id="events-0"] .event-attend-button').click()`)
  await until(`document.querySelector('.agenda-upcoming [data-event-id="events-0"] .event-attend-button').getAttribute('aria-pressed')==='true'`)
  await evaluate(`history.pushState({},'', '/profile?tab=events');dispatchEvent(new PopStateEvent('popstate'))`)
  await until(`Boolean(document.querySelector('[aria-label="Participaci\u00f3n"]'))&&Boolean(document.querySelector('[aria-label="Cancelar asistencia"]'))`)
  await evaluate(`document.querySelector('[aria-label="Participaci\u00f3n"]').querySelectorAll('button')[1].click()`)
  await until(`document.querySelector('[aria-label="Participaci\u00f3n"] button:nth-child(2)').getAttribute('aria-pressed')==='true'`)
  await evaluate(`document.querySelector('[aria-label="Cancelar asistencia"]').click()`)
  await until(`Boolean(document.querySelector('.personal-events-empty'))`)
  await evaluate(`document.querySelector('[aria-label="Participaci\u00f3n"] button:last-child').click()`)
  await until(`Boolean(document.querySelector('.personal-event-card'))`)
  await evaluate(`document.querySelector('[aria-label="Editar evento"]').click()`)
  await until(`Boolean(document.querySelector('.content-management-dialog input'))`)
  assert.match(await evaluate(`document.querySelector('#content-management-title').textContent`),/Editar evento/)
  await evaluate(`(()=>{const input=document.querySelector('.composer-title');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'Evento actualizado desde mi perfil');input.dispatchEvent(new Event('input',{bubbles:true}))})()`)
  await evaluate(`document.querySelector('.post-composer form,form.post-composer').requestSubmit()`)
  await until(`!document.querySelector('.content-management-dialog')`)
  await until(`document.querySelector('.personal-event-link')?.textContent==='Evento actualizado desde mi perfil'`)
  await evaluate(`document.querySelector('.personal-event-link').click()`)
  await until(`Boolean(document.querySelector('.mural-activity-dialog'))`)
  assert.equal(await evaluate(`new URL(location.href).searchParams.get('publication')`),'events-0')
  await send('Page.navigate',{url:`${app}/tests/fixtures/mural.html?count=8&role=lector`})
  await until(`Boolean(document.querySelector('a[href="/events"]'))`)
  await evaluate(`history.pushState({},'', '/profile?tab=events');dispatchEvent(new PopStateEvent('popstate'))`)
  await until(`Boolean(document.querySelector('.personal-events-empty'))`)
  assert.equal(await evaluate(`document.querySelector('[aria-label="Participaci\u00f3n"]')`),null)
  await evaluate(`document.querySelector('.reader-profile-tabs button:first-child').click()`)
  await until(`Boolean(document.querySelector('.reader-about-section'))`)
  assert.deepEqual(errors,[])
  console.log('PASS: five profile tabs, privacy, visitor read-only, nine themes at three widths, attendance synchronization/cancel, editing and original publication link')
}finally{ws.close();await fetch(`${cdp}/json/close/${target.id}`)}
