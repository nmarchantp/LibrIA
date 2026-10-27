import assert from 'node:assert/strict'

const cdp = process.env.CDP_URL || 'http://127.0.0.1:9224'
const app = process.env.VITE_URL || 'http://localhost:5173'
const target = await (await fetch(`${cdp}/json/new?about:blank`, { method: 'PUT' })).json()
const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise(resolve => { ws.onopen = resolve })
let sequence = 0
const pending = new Map()
ws.onmessage = event => {
  const message = JSON.parse(event.data)
  if (message.id) { pending.get(message.id)?.(message); pending.delete(message.id) }
}
const send = (method, params = {}) => new Promise(resolve => {
  pending.set(++sequence, resolve)
  ws.send(JSON.stringify({ id: sequence, method, params }))
})
const evaluate = async expression => {
  const response = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (response.result?.exceptionDetails) throw Error(JSON.stringify(response.result.exceptionDetails))
  return response.result.result.value
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
const until = async expression => {
  for (let attempt = 0; attempt < 100; attempt++) { if (await evaluate(expression)) return; await pause(50) }
  throw Error(`Timed out: ${expression}`)
}
const type = value => evaluate(`(()=>{const input=document.querySelector('input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(value)});input.dispatchEvent(new Event('input',{bubbles:true}));return true})()`)
try {
  await send('Page.navigate', { url: `${app}/tests/fixtures/book-search.html` })
  await until(`!!document.querySelector('input') && !!window.searchQA`)
  await type('b'); await pause(50); await type('book')
  await until(`document.querySelectorAll('.catalog-result-card').length===1`)
  assert.equal(await evaluate(`window.searchQA.requests.length`), 1, 'Debounce and StrictMode do not duplicate requests')
  assert.equal(await evaluate(`document.querySelector('.catalog-result-author').textContent`), 'Author')
  await evaluate(`document.querySelector('.catalog-result-list + .catalog-state button').click()`)
  await until(`document.querySelectorAll('.catalog-result-card').length===2`)
  assert.equal(await evaluate(`window.searchQA.requests.at(-1).start`), '40')
  await evaluate(`window.searchQA.delay=1000`)
  await type('old')
  await until(`window.searchQA.requests.at(-1).query==='old'`)
  await type('new')
  await until(`window.searchQA.aborted===1`)
  await until(`document.querySelector('.catalog-result-copy h2')?.textContent==='new 0'`)
  await evaluate(`window.searchQA.delay=20;window.searchQA.networkError=true`)
  await type('offline')
  await until(`document.querySelector('[role=alert]')?.textContent.includes('backend')`)
  await evaluate(`window.searchQA.networkError=false;document.querySelector('[role=alert] button').click()`)
  await until(`document.querySelector('.catalog-result-copy h2')?.textContent==='offline 0'`)
  assert.equal(await evaluate(`window.searchQA.requests.at(-1).refresh`), 'true')
  await type('empty')
  await until(`document.querySelector('.catalog-state h2')?.textContent==='No encontramos libros'`)
  await evaluate(`window.searchQA.openLibrary=true`)
  await type('fallback')
  await until(`document.querySelector('.catalog-result-copy h2')?.textContent==='fallback 0'`)
  await evaluate(`document.querySelector('.catalog-result-list + .catalog-state button').click()`)
  await until(`document.querySelectorAll('.catalog-result-card').length===2`)
  assert.equal(await evaluate(`window.searchQA.requests.at(-1).provider`), 'open_library')
  assert.equal(await evaluate(`window.searchQA.requests.at(-1).page`), '2')
  assert.equal(await evaluate(`window.searchQA.requests.at(-1).start`), null)
  await evaluate(`window.searchQA.rawResult={items:[{id:'available-during-outage',volumeInfo:{title:'Available book',authors:['Author']}}],partial:true,error_code:'external_unavailable',has_more:false,warning:'La búsqueda externa está temporalmente limitada; mostramos los resultados disponibles. Puedes reintentar más tarde.'}`)
  await type('outage')
  await until(`!!document.querySelector('[role=alert]') && document.querySelector('.catalog-result-copy h2')?.textContent==='Available book'`)
  assert.equal(await evaluate(`document.querySelectorAll('[role=alert]').length`), 1)
  assert.equal(await evaluate(`document.querySelector('[role=alert]').textContent.split('temporalmente limitada').length-1`), 1)
  assert.equal(await evaluate(`document.querySelector('[role=alert]').textContent.includes('pueden faltar libros')`), false)
  assert.equal(await evaluate(`!!document.querySelector('.catalog-result-list + .catalog-state button')`), false)
  assert.equal(await evaluate(`!!document.querySelector('[role=alert] button')`), true)
  if (process.env.OPEN_LIBRARY_REAL_RESULTS) {
    const { readFile } = await import('node:fs/promises')
    const queries = JSON.parse(await readFile(process.env.OPEN_LIBRARY_REAL_RESULTS, 'utf8'))
    for (const [query, result] of Object.entries(queries)) {
      assert.ok(result.items.length > 0)
      await evaluate(`window.searchQA.rawResult=${JSON.stringify(result)}`)
      await type(query)
      await until(`document.querySelectorAll('.catalog-result-card').length===${result.items.length}`)
      assert.equal(await evaluate(`document.querySelector('.catalog-result-copy h2').textContent`), result.items[0].volumeInfo.title)
      console.log(`PASS actual normalized Open Library results rendered: ${query}, ${result.items.length} Spanish editions`)
    }
  }
  console.log('PASS debounce, cancellation, pagination, forced retry, local connection error, empty and malformed results; no backend writes.')
} finally {
  ws.close()
  await fetch(`${cdp}/json/close/${target.id}`)
}
