import assert from 'node:assert/strict'
const cdp='http://127.0.0.1:9224', app='http://127.0.0.1:5173'
const target=await(await fetch(`${cdp}/json/new?about:blank`,{method:'PUT'})).json()
const ws=new WebSocket(target.webSocketDebuggerUrl)
await new Promise(resolve=>{ws.onopen=resolve})
let sequence=0
const pending=new Map(),errors=[]
ws.onmessage=event=>{const message=JSON.parse(event.data);if(message.method==='Runtime.exceptionThrown')errors.push(message.params);if(pending.has(message.id)){pending.get(message.id)(message);pending.delete(message.id)}}
const send=(method,params={})=>new Promise(resolve=>{pending.set(++sequence,resolve);ws.send(JSON.stringify({id:sequence,method,params}))})
async function evaluate(expression){const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.error||result.result?.exceptionDetails)throw Error(JSON.stringify(result));return result.result.result.value}
async function until(expression){for(let i=0;i<120;i++){if(await evaluate(expression))return;await new Promise(resolve=>setTimeout(resolve,50))}throw Error(`Timed out: ${expression}`)}
const fixture=`${app}/tests/fixtures/mural.html?count=6&persist_events=1`
const first='.mural-publication-event'
async function mural(){await evaluate(`document.querySelector('a[href="/"]').click()`);await until(`Boolean(document.querySelector('.mural-audiences'))`);await evaluate(`Array.from(document.querySelectorAll('.mural-audiences button')).find(button=>button.textContent==='Eventos').click()`);await until(`Boolean(document.querySelector('${first}'))`)}
async function calendar(){await evaluate(`document.querySelector('a[href="/events"]').click()`);await until(`Boolean(document.querySelector('.event-card'))`)}
async function change(name,value){await evaluate(`(()=>{const input=document.querySelector('[name="${name}"]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'${value}');input.dispatchEvent(new Event('input',{bubbles:true}))})()`)}
try{
  await send('Runtime.enable');await send('Emulation.setTimezoneOverride',{timezoneId:'UTC'})
  await send('Page.navigate',{url:fixture});await until(`Boolean(window.muralTest)`)
  await evaluate(`localStorage.removeItem('libria-event-test-state')`)
  await send('Page.navigate',{url:fixture});await until(`Boolean(document.querySelector('.mural-audiences'))`)
  await mural()
  assert.equal(await evaluate(`document.querySelector('${first} .event-date strong').textContent`),'12')
  assert.equal(await evaluate(`document.querySelector('${first} .post-gallery-overflow').textContent`),'+3')
  await evaluate(`document.querySelector('${first} .event-attend-button').click();document.querySelector('${first} .event-attend-button').click()`)
  await until(`document.querySelector('${first} .event-attend-button').getAttribute('aria-pressed')==='true'`)
  assert.equal(await evaluate(`window.muralTest.requests.filter(request=>request.path==='/api/events/events-0/attendance'&&request.method==='PUT').length`),1)
  await calendar()
  assert.equal(await evaluate(`document.querySelector('.event-card .event-attend-button').getAttribute('aria-pressed')`),'true')
  await evaluate(`document.querySelector('.event-card .event-edit-button').click()`)
  await until(`Boolean(document.querySelector('[name="event_start_date"]'))`)
  assert.equal(await evaluate(`document.querySelector('[name="event_start_date"]').value`),'2026-11-12')
  assert.equal(await evaluate(`document.querySelectorAll('.composer-thumbs img').length`),6)
  await change('event_start_date','2026-11-13');await change('event_start_time','19:30')
  await evaluate(`document.querySelector('.post-composer').requestSubmit()`)
  await until(`!document.querySelector('.content-management-dialog')`)
  await until(`Array.from(document.querySelectorAll('.event-card')).some(card=>card.textContent.includes('Stella a Chile')&&card.querySelector('.event-date strong').textContent==='13')`)
  await mural()
  assert.equal(await evaluate(`document.querySelector('${first} .event-date strong').textContent`),'13')
  assert.equal(await evaluate(`document.querySelector('${first} .event-attend-button').getAttribute('aria-pressed')`),'true')
  assert.equal(await evaluate(`Boolean(document.querySelector('${first} .event-schedule-update'))`),false)
  for(const theme of ['lavanda','otono','invierno','bosque','rosa-antiguo','dark','dark-rosado','dark-blood','dark-dorado']){
    await evaluate(`import('/src/theme/themes.js').then(module=>module.applyTheme('${theme}'))`)
    for(const width of [1440,768,390,320]){
      await send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<500})
      assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth&&Array.from(document.querySelectorAll('.mural-publication-event')).every(card=>card.scrollWidth<=card.clientWidth+1)`),true,`${theme}/${width}`)
      const tiles=await evaluate(`Array.from(document.querySelector('${first}').querySelectorAll('.post-gallery-tile'),tile=>{const r=tile.getBoundingClientRect();return {top:r.top,width:r.width,height:r.height}})`)
      assert.ok(tiles.length===4&&tiles.every(tile=>Math.abs(tile.top-tiles[0].top)<1&&Math.abs(tile.width-tile.height)<1),`${theme}/${width}: ${JSON.stringify(tiles)}`)
    }
  }
  await send('Page.navigate',{url:fixture});await until(`Boolean(document.querySelector('.mural-audiences'))`);await mural()
  assert.equal(await evaluate(`document.querySelector('${first} .event-date strong').textContent`),'13')
  assert.equal(await evaluate(`document.querySelector('${first} .event-attend-button').getAttribute('aria-pressed')`),'true')
  await evaluate(`document.querySelector('${first} .event-attend-button').click()`)
  await until(`document.querySelector('${first} .event-attend-button').getAttribute('aria-pressed')==='false'`)
  await calendar()
  assert.equal(await evaluate(`Array.from(document.querySelectorAll('.event-card')).find(card=>card.textContent.includes('Stella a Chile')).querySelector('.event-attend-button').getAttribute('aria-pressed')`),'false')
  await evaluate(`document.querySelector('.event-edit-button').click()`);await until(`Boolean(document.querySelector('.event-delete-zone'))`)
  await evaluate(`document.querySelector('.event-delete-zone>button').click()`)
  await until(`Boolean(document.querySelector('.event-delete-zone [role=alertdialog]'))`)
  await evaluate(`document.querySelector('.event-delete-zone [role=alertdialog] button:last-child').click()`)
  await until(`!document.querySelector('.content-management-dialog')&&!Array.from(document.querySelectorAll('.event-card')).some(card=>card.textContent.includes('Stella a Chile'))`)
  await mural()
  assert.equal(await evaluate(`Array.from(document.querySelectorAll('.mural-publication-event')).some(card=>card.textContent.includes('Stella a Chile'))`),false)
  assert.deepEqual(errors,[])
  console.log('PASS: attendance, duplicate-click guard, calendar editing, reschedule preserves attendance, reload, cancellation, deletion, UTC display and nine responsive themes')
}finally{await evaluate(`localStorage.removeItem('libria-event-test-state')`).catch(()=>{});ws.close();await fetch(`${cdp}/json/close/${target.id}`)}
