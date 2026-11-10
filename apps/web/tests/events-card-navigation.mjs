import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
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
  await send('Runtime.enable')
  await send('Emulation.setDeviceMetricsOverride',{width:1536,height:1100,deviceScaleFactor:1,mobile:false})
  await send('Page.navigate',{url:`${app}/tests/fixtures/mural.html?count=8&agenda=1&role=admin`})
  await until(`Boolean(document.querySelector('a[href="/events"]'))`)
  await evaluate(`document.querySelector('a[href="/events"]').click()`)
  await until(`Boolean(document.querySelector('.agenda-upcoming [data-event-id="events-0"]'))`)
  const attend=await evaluate(`(()=>{const card=document.querySelector('.agenda-upcoming [data-event-id="events-0"]');card.scrollIntoView({block:'center',inline:'center',behavior:'instant'});const rect=card.querySelector('.event-attend-button').getBoundingClientRect();return {x:rect.left+rect.width/2,y:rect.top+rect.height/2}})()`)
  await send('Input.dispatchMouseEvent',{type:'mousePressed',x:attend.x,y:attend.y,button:'left',clickCount:1})
  await send('Input.dispatchMouseEvent',{type:'mouseReleased',x:attend.x,y:attend.y,button:'left',clickCount:1})
  await until(`document.querySelector('.agenda-upcoming [data-event-id="events-0"] .event-attend-button').getAttribute('aria-pressed')==='true'`)
  assert.equal(await evaluate(`location.pathname`),'/events','Attendance does not navigate')
  const point=await evaluate(`(()=>{const card=document.querySelector('.agenda-upcoming [data-event-id="events-0"]');card.scrollIntoView({block:'center',inline:'center',behavior:'instant'});const rect=card.getBoundingClientRect(),x=rect.right-25,y=rect.bottom-25;return {x,y,hit:document.elementFromPoint(x,y)?.outerHTML.slice(0,200)}})()`)
  await send('Input.dispatchMouseEvent',{type:'mousePressed',x:point.x,y:point.y,button:'left',clickCount:1})
  await send('Input.dispatchMouseEvent',{type:'mouseReleased',x:point.x,y:point.y,button:'left',clickCount:1})
  await until(`Boolean(document.querySelector('.mural-activity-dialog'))`)
  assert.equal(await evaluate(`new URL(location.href).searchParams.get('publication')`),'events-0')
  assert.equal(await evaluate(`document.querySelector('.mural-activity-dialog .event-attend-button').getAttribute('aria-pressed')`),'true')
  assert.deepEqual(errors,[])
  console.log('PASS: card whitespace opens original publication, attendance remains independent and synchronized')
}finally{ws.close();await fetch(`${cdp}/json/close/${target.id}`)}
