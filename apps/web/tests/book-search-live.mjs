// Full React app, real bibliographic endpoints, isolated browser context.
// Only authentication and personal-data reads are stubbed. Private writes blocked.
import assert from 'node:assert/strict'
const cdp = process.env.CDP_URL || 'http://127.0.0.1:9224'
const base = process.env.VITE_URL || 'http://localhost:5173'
const query = 'El infinito en un junco'
async function connect(url) {
  const ws = new WebSocket(url)
  await new Promise(resolve => { ws.onopen = resolve })
  let sequence = 0
  const pending = new Map()
  ws.onmessage = event => { const m = JSON.parse(event.data); if (m.id) { pending.get(m.id)?.(m); pending.delete(m.id) } }
  const send = (method, params = {}) => new Promise(resolve => { pending.set(++sequence, resolve); ws.send(JSON.stringify({ id: sequence, method, params })) })
  return { ws, send }
}
const version = await (await fetch(`${cdp}/json/version`)).json()
const browser = await connect(version.webSocketDebuggerUrl)
const context = await browser.send('Target.createBrowserContext')
assert.ok(context.result?.browserContextId, 'Requires an isolated browser context')
const created = await browser.send('Target.createTarget', { url: 'about:blank', browserContextId: context.result.browserContextId })
const targets = await (await fetch(`${cdp}/json/list`)).json()
const page = await connect(targets.find(t => t.id === created.result.targetId).webSocketDebuggerUrl)
const evaluate = async expression => {
  const result = await page.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.result?.exceptionDetails) throw Error(JSON.stringify(result.result.exceptionDetails))
  return result.result.result.value
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
const until = async expression => {
  for (let i = 0; i < 160; i++) { if (await evaluate(expression)) return; await pause(500) }
  throw Error(`Timed out: ${expression}`)
}
try {
  await page.send('Page.enable')
  await page.send('Page.addScriptToEvaluateOnNewDocument', { source: `
    localStorage.setItem('libria_token','isolated-browser-diagnostic');
    window.bookResponses=[];
    const actualFetch=window.fetch.bind(window);
    window.fetch=async(url,options={})=>{
      const parsed=new URL(String(url),location.href);
      const path=parsed.pathname;
      const reply=data=>Promise.resolve(new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}}));
      if(path==='/api/auth/me')return reply({id:'isolated-diagnostic',display_name:'Diagnóstico',role:'lector',capabilities:[]});
      if(path==='/api/readings/me')return reply([]);
      if(path==='/api/analytics/access')return reply({group:false});
      if(path.startsWith('/api/') && options.method && options.method.toUpperCase()!=='GET')throw Error('Private writes blocked');
      const response=await actualFetch(url,options);
      if(path.startsWith('/api/books')){
        const data=await response.clone().json().catch(()=>null);
        window.bookResponses.push({url:String(url),status:response.status,data});
      }
      return response;
    };` })
  const navigation = await page.send('Page.navigate', { url: `${base}/books` })
  assert.ok(!navigation.result?.errorText, JSON.stringify(navigation))
  await until(`!!document.querySelector('.catalog-search-input input')`)
  await evaluate(`document.querySelector('[role=tab]').click()`)
  await evaluate(`(()=>{const input=document.querySelector('.catalog-search-input input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(query)});input.dispatchEvent(new Event('input',{bubbles:true}));return true})()`)
  await until(`window.bookResponses.some(r=>new URL(r.url).searchParams.get('q')===${JSON.stringify(query)}) && !document.querySelector('.catalog-result-list[aria-busy=true]')`)
  const response = await evaluate(`window.bookResponses.find(r=>new URL(r.url).searchParams.get('q')===${JSON.stringify(query)})`)
  assert.equal(new URL(response.url).searchParams.get('search_by'), 'title')
  console.log(JSON.stringify({ actualRequest: response.url, http: response.status, totalItems: response.data.totalItems, provider: response.data.active_provider, partial: response.data.partial || false, warning: response.data.warning || null, titles: response.data.items?.map(item => item.volumeInfo?.title) }))
  assert.ok(response.data.items?.length > 0, 'Real search must return a book; provider may be temporarily unavailable')
  assert.equal(await evaluate(`!!document.querySelector('.catalog-result-card')`), true)
  assert.equal(await evaluate(`!!document.querySelector('[role=alert]')`), false)
  await evaluate(`(()=>{const links=[...document.querySelectorAll('.catalog-result-card')];const exact=links.find(a=>a.querySelector('h2').textContent.toLowerCase()===${JSON.stringify(query.toLowerCase())});(exact||links[0]).click();return true})()`)
  await until(`!!document.querySelector('.detail-intro h1')`)
  const title = await evaluate(`document.querySelector('.detail-intro h1').textContent`)
  assert.match(title.toLowerCase(), /infinito en un junco/)
  console.log(`PASS real React search with Título, real backend JSON, no warning, and book detail opened: ${title}`)
} catch (error) {
  console.log(await evaluate(`({url:location.href,title:document.title,ready:document.readyState,text:document.body?.innerText.slice(0,200)})`))
  throw error
} finally {
  page.ws.close()
  await browser.send('Target.disposeBrowserContext', { browserContextId: context.result.browserContextId })
  browser.ws.close()
}
