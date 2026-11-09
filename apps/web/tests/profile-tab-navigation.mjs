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
async function select(value){
  await evaluate(`(()=>{const tabs=[...document.querySelectorAll('[aria-label="Secciones de mi perfil"] button')];tabs[${JSON.stringify({about:0,library:1,activity:2,events:3,analysis:4}[value])}].click()})()`)
  await until(`document.querySelector('[data-profile-panel="${value}"]')?.hidden===false`)
  await until(`![...document.querySelectorAll('[data-profile-panel="${value}"] [role="status"]')].some(node=>/Cargando|Consultando/.test(node.textContent))`)
  assert.equal(await evaluate(`new URL(location.href).searchParams.get('tab')`),value)
  assert.equal(await evaluate(`document.querySelectorAll('[data-profile-panel]:not([hidden])').length`),1)
  assert.equal(await evaluate(`window.profileHeader===document.querySelector('.reader-profile-identity')&&window.profileRoot===document.querySelector('.profile-page')&&window.documentToken==='same-document'`),true,'Header, React root and document remain mounted')
}
try{
  await send('Runtime.enable')
  await send('Emulation.setDeviceMetricsOverride',{width:1536,height:1100,deviceScaleFactor:1,mobile:false})
  await send('Page.navigate',{url:`${app}/tests/fixtures/mural.html?count=8&role=admin`})
  await until(`Boolean(document.querySelector('a[href="/events"]'))`)
  await evaluate(`history.pushState({},'', '/profile?tab=about');dispatchEvent(new PopStateEvent('popstate'))`)
  await until(`Boolean(document.querySelector('.reader-about-section'))`)
  await evaluate(`window.documentToken='same-document';window.profileHeader=document.querySelector('.reader-profile-identity');window.profileRoot=document.querySelector('.profile-page');void 0`)
  assert.equal(await evaluate(`document.querySelectorAll('[data-profile-panel]').length`),1,'No eager panels')
  await select('activity');await select('events');await select('library')
  await evaluate(`document.querySelector('.reader-library-filters button:nth-child(2)').click()`)
  await select('analysis')
  const before=await evaluate(`window.muralTest.requests.length`)
  for(const width of [1536,390]){
    await send('Emulation.setDeviceMetricsOverride',{width,height:1100,deviceScaleFactor:1,mobile:width<500})
    for(const name of ['about','activity','events','library','analysis'])await select(name)
    assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth+1`),true)
  }
  const requests=await evaluate(`window.muralTest.requests.slice(${before})`)
  assert.deepEqual(requests,[],'Revisiting tabs reuses panel data')
  assert.equal(await evaluate(`document.querySelector('.reader-library-filters button:nth-child(2)').getAttribute('aria-pressed')`),'true','Library filter is preserved')
  await evaluate(`history.back()`)
  await until(`new URL(location.href).searchParams.get('tab')==='library'`)
  assert.equal(await evaluate(`document.querySelector('[data-profile-panel="library"]').hidden`),false)
  await evaluate(`history.forward()`)
  await until(`new URL(location.href).searchParams.get('tab')==='analysis'`)
  assert.equal(await evaluate(`document.querySelector('[data-profile-panel="analysis"]').hidden`),false)
  await select('events')
  await evaluate(`(()=>{const select=document.querySelector('.personal-events-privacy select');Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(select,'public');select.dispatchEvent(new Event('change',{bubbles:true}))})()`)
  await until(`document.querySelector('.personal-events-privacy select').value==='public'&&!document.querySelector('.personal-events-privacy select').disabled`)
  await evaluate(`history.pushState({},'', '/profiles/visitor?tab=events');dispatchEvent(new PopStateEvent('popstate'))`)
  await until(`Boolean(document.querySelector('.reader-community-profile [data-profile-panel="events"]:not([hidden])'))`)
  await evaluate(`window.publicHeader=document.querySelector('.reader-profile-identity');window.publicRequests=window.muralTest.requests.length;document.querySelector('[aria-label="Secciones del perfil"] button:first-child').click()`)
  await until(`Boolean(document.querySelector('.reader-community-profile [data-profile-panel="about"]:not([hidden])'))`)
  await evaluate(`document.querySelector('[aria-label="Secciones del perfil"] button:last-child').click()`)
  await until(`Boolean(document.querySelector('.reader-community-profile [data-profile-panel="events"]:not([hidden])'))`)
  assert.equal(await evaluate(`window.publicHeader===document.querySelector('.reader-profile-identity')`),true)
  assert.equal(await evaluate(`window.muralTest.requests.length===window.publicRequests`),true)
  await evaluate(`history.replaceState({},'', '/tests/fixtures/mural.html?count=8&role=admin&profile_tab=events')`)
  await send('Page.reload')
  await until(`Boolean(document.querySelector('.reader-profile-identity'))`)
  await until(`Boolean(document.querySelector('[data-profile-panel="events"]:not([hidden])'))`)
  assert.equal(await evaluate(`new URL(location.href).searchParams.get('tab')`),'events','Manual reload restores selected tab')
  assert.deepEqual(errors,[])
  console.log('PASS: five tabs without reload/remount, lazy data and no repeat requests, retained library filter, back/forward, public profile, deep link/manual reload, desktop/mobile')
}finally{ws.close();await fetch(`${cdp}/json/close/${target.id}`)}
