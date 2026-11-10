import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'

const cdp = process.env.CDP_URL || 'http://127.0.0.1:9224'
const app = process.env.VITE_URL || 'http://127.0.0.1:5173'
const target = await (await fetch(`${cdp}/json/new?about:blank`, { method: 'PUT' })).json()
const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject })
let sequence = 0
const pending = new Map()
ws.onmessage = event => { const message = JSON.parse(event.data); if (pending.has(message.id)) { pending.get(message.id)(message); pending.delete(message.id) } }
const send = (method, params = {}) => new Promise(resolve => { pending.set(++sequence, resolve); ws.send(JSON.stringify({ id: sequence, method, params })) })
const evaluate = async expression => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.error || result.result?.exceptionDetails) throw new Error(JSON.stringify(result))
  return result.result.result.value
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
async function until(expression) {
  for (let n = 0; n < 100; n++) { if (await evaluate(expression)) return; await pause(50) }
  throw new Error(`Timed out: ${expression}`)
}
try {
  await send('Page.navigate', { url: `${app}/tests/fixtures/feed-progress.html` })
  await until(`document.querySelectorAll('.feed-card-progress').length === 4`)
  await evaluate('document.fonts.ready')
  await until(`document.querySelector('.post-progress-author')?.textContent === 'Autora de prueba'`)
  await until(`!document.querySelectorAll('.feed-card-progress')[3].querySelector('.book-cover img')`)
  for (const theme of ['lavanda', 'otono', 'invierno', 'bosque', 'rosa-antiguo', 'dark', 'dark-rosado', 'dark-blood', 'dark-dorado']) {
    await evaluate(`import('/src/theme/themes.js').then(module => module.applyTheme('${theme}'))`)
    for (const width of [1440, 768, 390, 320]) {
      await send('Emulation.setDeviceMetricsOverride', { width, height: 1100, deviceScaleFactor: 1, mobile: width < 500 })
      const metrics = await evaluate(`Array.from(document.querySelectorAll('.feed-card-progress'), card => {
        const rect = card.getBoundingClientRect(), cover = card.querySelector('.book-cover').getBoundingClientRect();
        const title = card.querySelector('.post-progress-title').textContent;
        return {height:rect.height, width:rect.width, cover:cover.width, overflow:card.scrollWidth > card.clientWidth + 1, duplicates:card.innerText.split(title).length - 1, nested:!!card.querySelector('.post-book'), badge:getComputedStyle(card.querySelector('.post-kind')).display, touch:card.querySelector('.comments-toggle').getBoundingClientRect().height, value:card.querySelector('progress').value};
      })`)
      for (const card of metrics) {
        assert.ok(card.width <= 640 && card.cover >= 65 && card.cover <= 80, `${theme}/${width}: proportion`)
        assert.ok(!card.overflow && card.duplicates === 1 && !card.nested, `${theme}/${width}: clean content`)
        assert.ok(card.touch >= 44, `${theme}/${width}: touch target`)
        assert.notEqual(card.badge, 'none', `${theme}/${width}: progress badge visible`)
        assert.ok(card.height < (width < 500 ? 480 : 360), `${theme}/${width}: compact height ${card.height}`)
      }
      assert.deepEqual(metrics.map(card => card.value), [16, 100, 16, 100])
      assert.equal(await evaluate(`document.documentElement.scrollWidth <= innerWidth`), true)
    }
  }
  assert.equal(await evaluate(`document.querySelector('.feed-card-progress .post-text').textContent`), 'Llegó al 16 % de su lectura.')
  assert.equal(await evaluate(`document.querySelectorAll('.feed-card:not(.feed-card-progress) .review-rating').length`), 1)
  assert.equal(await evaluate(`document.querySelector('.post-progress-book-link').getAttribute('href')`), '/books/sixteen')
  await evaluate(`document.querySelector('.comments-toggle').click()`)
  await until(`document.querySelector('.comment-item')?.textContent.includes('¡Buen avance!')`)
  assert.equal(await evaluate(`document.querySelector('.comments-toggle').getAttribute('aria-expanded')`), 'true')
  assert.ok((await evaluate('window.feedTestRequests')).some(request => request.url.endsWith('/posts/sixteen/comments')))
  await evaluate(`document.querySelector('.comments-toggle').click()`)
  assert.equal(await evaluate(`document.querySelector('.comments-toggle').getAttribute('aria-expanded')`), 'false')
  const out = new URL('../../../artifacts/feed-progress/', import.meta.url)
  await mkdir(out, { recursive: true })
  for (const [label, width] of [['desktop', 1440], ['mobile', 390]]) {
    await send('Emulation.setDeviceMetricsOverride', { width, height: 1100, deviceScaleFactor: 1, mobile: width < 500 })
    await evaluate(`import('/src/theme/themes.js').then(module => module.applyTheme('lavanda'));document.querySelector('.feed-posts').scrollIntoView()`)
    const shot = await send('Page.captureScreenshot', { format: 'png' })
    await writeFile(new URL(`${label}.png`, out), Buffer.from(shot.result.data, 'base64'))
  }
  console.log('PASS: 16%/100%, long titles, missing/broken covers, four widths, nine themes, compact dimensions, single titles, book links and comments; review unchanged.')
} finally { ws.close(); await fetch(`${cdp}/json/close/${target.id}`) }
