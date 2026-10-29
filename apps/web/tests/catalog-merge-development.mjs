// Actual development UI + REST + PostgreSQL. No HTTP mocks or provider requests.
import assert from 'node:assert/strict'
import fs from 'node:fs'
const fixture=JSON.parse(fs.readFileSync('../../tmp/catalog-phase7-fixture.json','utf8'))
const cdp=process.env.CDP_URL || 'http://127.0.0.1:9237'
const app=process.env.VITE_URL || 'http://127.0.0.1:5173'
const target=await (await fetch(`${cdp}/json/new?about:blank`,{method:'PUT'})).json()
const ws=new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject})
let sequence=0;const pending=new Map()
ws.onmessage=event=>{const m=JSON.parse(event.data);if(pending.has(m.id)){pending.get(m.id)(m);pending.delete(m.id)}}
const send=(method,params={})=>new Promise(resolve=>{pending.set(++sequence,resolve);ws.send(JSON.stringify({id:sequence,method,params}))})
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.error){if(/context|navigat/i.test(r.error.message))return null;throw Error(r.error.message)}if(r.result.exceptionDetails)throw Error(JSON.stringify(r.result.exceptionDetails));return r.result.result.value}
async function until(expression){for(let n=0;n<200;n++){if(await evaluate(`Boolean(${expression})`))return;await new Promise(r=>setTimeout(r,50))}throw Error(`Timed out: ${expression}`)}
async function input(selector,value){await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});const proto=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(el,${JSON.stringify(value)});el.dispatchEvent(new Event('input',{bubbles:true}))})()`)}
async function click(label){await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent===${JSON.stringify(label)}).click()`)}
async function api(path,body){return evaluate(`(async()=>{const {API_URL}=await import('/src/api/client.js');const r=await fetch(API_URL+${JSON.stringify(path)},{headers:{Authorization:'Bearer '+localStorage.getItem('libria_token'),'Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()},...( ${JSON.stringify(body ?? null)}===null?{}:{method:'POST',body:JSON.stringify(${JSON.stringify(body ?? null)})})});const data=await r.json();if(!r.ok)throw Error('HTTP '+r.status+' '+JSON.stringify(data));return data})()`)}
const report={http_mocked:false,database:'local development libria',marker:fixture.marker,steps:[]}
try {
  await send('Network.clearBrowserCookies')
  await send('Storage.clearDataForOrigin',{origin:app,storageTypes:'local_storage'})
  await send('Page.navigate',{url:app+'/login'})
  await until("document.querySelector('input[name=email]')")
  await input('input[name=email]',fixture.email);await input('input[name=password]',fixture.password)
  await evaluate("document.querySelector('form').requestSubmit()")
  await until("!!localStorage.getItem('libria_token')")
  const access=await api('/roles/access');assert.equal(access.admin,true);assert.equal(access.catalog_merge,true)
  report.steps.push('Actual login with reader-role account and effective administrator permission')
  const readings=[];const reviews=[]
  for(const [i,book] of fixture.books.entries()) {
    if(process.argv.includes('--reuse')) {
      const attempts=await api('/readings/library/'+book.physical_work_id+'/attempts')
      readings.push(attempts[0].reading_id)
      reviews.push((await api('/reviews/by-book/'+book.physical_work_id)).items[0].id)
      continue
    }
    const library=await api('/readings/library',{book_ref:book.physical_work_id,book_title:fixture.title,edition_id:book.edition_id,edition_selected:true})
    const started=await api('/readings/events',{book_ref:book.physical_work_id,book_title:fixture.title,edition_id:book.edition_id,event:'start',page_count:120+i*120})
    await api('/readings/events',{book_ref:book.physical_work_id,book_title:fixture.title,reading_id:started.reading_id,event:'progress',current_page:5+i,page_count:120+i*120})
    readings.push(started.reading_id)
    const review=await api('/reviews',{work_id:book.physical_work_id,edition_id:book.edition_id,body:'Reseña sintética del recorrido real fase 7 '+i,rating:i===0?5:1,status:'published'})
    reviews.push(review.id)
  }
  report.steps.push('Created library memberships, selected editions, reading attempts, progress and two reviews through real REST')
  await send('Page.navigate',{url:app+'/admin/catalog'})
  await until("document.querySelector('h1')?.textContent==='Comparación de obras'")
  await input('form input',fixture.title);await click('Buscar')
  await until("document.querySelectorAll('li button').length>=4")
  for(const [i,label] of ['Seleccionar origen','Seleccionar destino canónico'].entries()) {
    await evaluate(`[...document.querySelectorAll('li')].find(li=>li.textContent.includes(${JSON.stringify(fixture.books[i].physical_work_id)})).querySelectorAll('button')[${i}].click()`)
  }
  await click('Comparar');await until("document.body.textContent.includes('Impacto previsto')")
  await click('Simular fusión');await until("document.body.textContent.includes('Resolución explícita de conflictos')")
  await evaluate(`document.querySelector('input[type=radio][value="${reviews[0]}"]').click()`)
  await evaluate("document.querySelector('fieldset input[type=checkbox]').click()")
  await input('fieldset textarea','Confirmación controlada: misma obra sintética, dos ediciones distintas')
  await input('fieldset input:not([type])','FUSIONAR')
  await click('Confirmar fusión administrativa')
  await until("[...document.querySelectorAll('[role=status]')].some(element=>element.textContent.includes('merged'))")
  report.steps.push('Compared, simulated, explicitly chose older review and destination metadata, then confirmed fusion in UI')
  const source=fixture.books[0].physical_work_id,targetWork=fixture.books[1].physical_work_id
  const detail=await api('/books/'+source);assert.equal(detail.libria.workId,targetWork)
  assert.equal(detail.libria.ratingsCount,1);assert.equal(detail.libria.averageRating,5)
  const library=await api('/readings/me');assert.equal(library.length,1)
  const attempts=await api('/readings/library/'+source+'/attempts');assert.equal(attempts.filter(r=>readings.includes(r.reading_id)).length,2)
  const publicReviews=await api('/reviews/by-book/'+source);assert.equal(publicReviews.items.length,1);assert.equal(publicReviews.items[0].id,reviews[0])
  assert.equal(detail.libria.readingStats.reading,1)
  const search=await api('/books?q='+encodeURIComponent(fixture.title))
  assert.deepEqual(search.items.filter(item=>item.libria?.workId===targetWork).map(item=>item.libria.workId),[targetWork])
  assert.equal(search.items.some(item=>item.libria?.workId===source),false)
  report.public_search={canonical_results:1,partial:!!search.partial,active_provider:search.active_provider}
  report.steps.push('Verified canonical detail, one membership, both reading attempts, selected public review, rating 5 and one active reader')
  const history=await api('/admin/catalog/history');const operation=history.find(o=>o.source_work_id===source && o.target_work_id===targetWork && o.active)
  assert.ok(operation);report.merge_operation_id=operation.id
  await send('Page.navigate',{url:app+'/books/'+source})
  await until(`location.pathname==='/books/${targetWork}'`)
  report.steps.push('Verified real public search returns canonical work and historical detail URL navigates to canonical URL')
  await send('Page.navigate',{url:app+'/admin/catalog'})
  await until("document.querySelector('h1')?.textContent==='Comparación de obras'")
  await click('Consultar historial administrativo')
  await until(`document.body.textContent.includes('${operation.id}')`)
  // Resolve recovery via the exact operation row, not another developer operation.
  await evaluate(`[...document.querySelectorAll('li')].find(li=>li.textContent.includes(${JSON.stringify(operation.id)})).querySelector('button').click()`)
  await until("document.body.textContent.includes('Simulación de separación')")
  const recovery=await api('/admin/catalog/merges/'+operation.id+'/reversal-preview',{})
  assert.deepEqual(recovery.blockers,[])
  // Read-only checks must not be mistaken for subsequent bibliographic activity.
  await input('article textarea','Reversión controlada del recorrido real fase 7')
  await input('article input:not([type])','REVERTIR')
  await click('Confirmar reversión administrativa')
  await until("[...document.querySelectorAll('[role=status]')].some(element=>element.textContent.includes('reversed'))")
  assert.equal((await api('/books/'+source)).libria.workId,source)
  assert.equal((await api('/readings/me')).length,2)
  assert.equal((await api('/reviews/by-book/'+source)).items[0].id,reviews[0])
  assert.equal((await api('/reviews/by-book/'+targetWork)).items[0].id,reviews[1])
  report.steps.push('Simulated and confirmed controlled reversal in UI; verified original work identities, memberships and reviews')
  report.success=true;report.reading_ids=readings;report.review_ids=reviews
  fs.writeFileSync('../../docs/catalog-canonical-phase7-browser-results.json',JSON.stringify(report,null,2)+'\n')
  console.log('PASS: real login → compare → preview → conflict selection → merge → verify → reverse → verify')
} catch(error) {
  report.success=false;report.error=String(error)
  fs.writeFileSync('../../docs/catalog-canonical-phase7-browser-results.json',JSON.stringify(report,null,2)+'\n')
  throw error
} finally {await send('Page.close');ws.close()}
