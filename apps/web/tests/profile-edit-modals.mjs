// Browser regression checks without extra dependencies. Requires Vite and an
// isolated Chromium/Edge exposing CDP_URL (default http://127.0.0.1:9224).
import assert from 'node:assert/strict'

const cdp = process.env.CDP_URL || 'http://127.0.0.1:9224'
const app = process.env.VITE_URL || 'http://127.0.0.1:5173'
const fixture = `${app}/tests/fixtures/profile-modals.html`
const target = await (await fetch(`${cdp}/json/new?about:blank`, { method: 'PUT' })).json()
const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject })
let sequence = 0
const pending = new Map()
ws.onmessage = event => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message)
    pending.delete(message.id)
  }
}
const send = (method, params = {}) => new Promise(resolve => {
  pending.set(++sequence, resolve)
  ws.send(JSON.stringify({ id: sequence, method, params }))
})
const evaluate = async expression => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.error || result.result?.exceptionDetails) throw new Error(JSON.stringify(result.error || result.result.exceptionDetails))
  return result.result.result.value
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
async function until(expression) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (await evaluate(expression)) return
    await pause(50)
  }
  throw new Error(`Timed out: ${expression}`)
}
async function key(key, code, shift = false) {
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key, code: key, windowsVirtualKeyCode: code, modifiers: shift ? 8 : 0 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key, code: key, windowsVirtualKeyCode: code, modifiers: shift ? 8 : 0 })
  await pause(30)
}
async function button(text) {
  await evaluate(`[...document.querySelectorAll('dialog[open] button')].find(button => button.textContent.trim() === ${JSON.stringify(text)}).click()`)
  await pause(40)
}
async function input(selector, value) {
  await evaluate(`(() => { const element = document.querySelector(${JSON.stringify(selector)}); Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value').set.call(element, ${JSON.stringify(value)}); element.dispatchEvent(new Event('input', { bubbles:true })); })()`)
  await pause(30)
}
async function open(section) {
  await evaluate(`(() => {
    window.qaRects = [...document.querySelectorAll('.reader-about-grid>.reader-personal-card')].map(element => { const r=element.getBoundingClientRect(); return [r.x,r.y,r.width,r.height] });
    window.qaBeforeScroll = scrollY;
    window.qaOpener = document.querySelector(${JSON.stringify(`${section} .reader-edit-button`)});
    window.qaOpener.focus({preventScroll:true}); window.qaOpener.click();
  })()`)
  await until(`Boolean(document.querySelector('dialog[open]'))`)
  await pause(60)
  const opening = await evaluate(`(() => {
    const dialog=document.querySelector('dialog[open]');
    const stable=[...document.querySelectorAll('.reader-about-grid>.reader-personal-card')].every((element,i)=>{const r=element.getBoundingClientRect();return [r.x,r.y,r.width,r.height].every((value,j)=>Math.abs(value-window.qaRects[i][j])<.5)});
    return {stable,scroll:scrollY-window.qaBeforeScroll,locked:document.body.style.overflow==='hidden',portal:dialog.parentElement===document.body,modal:dialog.matches(':modal'),focused:dialog.contains(document.activeElement),inline:!!document.querySelector('.reader-about-grid form')};
  })()`)
  if (!opening.focused) console.log('Focus diagnostic', section, await evaluate(`({width:innerWidth,active:document.activeElement?.outerHTML.slice(0,180),dialog:document.querySelector('dialog')?.textContent.slice(0,90)})`))
  assert.deepEqual(opening, {stable:true,scroll:0,locked:true,portal:true,modal:true,focused:true,inline:false}, `Opening ${section} must preserve layout and focus`)
}
async function closed() {
  await until(`!document.querySelector('dialog[open]')`)
  assert.equal(await evaluate(`document.activeElement===window.qaOpener && document.body.style.overflow!=='hidden'`), true, 'Restore opener focus and background scroll')
}

try {
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  await send('Page.navigate', { url: fixture })
  await until(`document.querySelectorAll('.reader-about-grid>.reader-personal-card').length===5`)
  await evaluate(`document.fonts.ready.then(()=>true)`)
  await pause(100)
  await open('.reader-story')
  assert.equal(await evaluate(`document.activeElement.tagName`), 'TEXTAREA')
  // Keyboard focus must cycle inside the modal, including reverse Tab.
  await evaluate(`document.querySelector('dialog .reader-modal-footer button[type=submit]').focus()`)
  await key('Tab', 9)
  assert.equal(await evaluate(`document.activeElement.classList.contains('reader-modal-close')`), true)
  await key('Tab', 9, true)
  assert.equal(await evaluate(`document.activeElement.type==='submit'`), true)
  await evaluate(`window.qaOpener.focus()`)
  assert.equal(await evaluate(`document.querySelector('dialog').contains(document.activeElement)`), true, 'Background must be inert')
  await input('dialog textarea', 'Borrador sin guardar')
  assert.equal(await evaluate(`document.querySelector('.reader-biography').textContent`), 'Historia guardada')
  await button('Cancelar')
  await until(`document.querySelector('dialog h2').textContent.includes('Descartar')`)
  assert.equal(await evaluate(`document.activeElement.textContent`), 'Seguir editando')
  await button('Seguir editando')
  assert.equal(await evaluate(`document.querySelector('dialog textarea').value`), 'Borrador sin guardar')
  await evaluate(`document.querySelector('.reader-modal-close').click()`)
  await until(`document.querySelector('dialog h2').textContent.includes('Descartar')`)
  await key('Escape', 27)
  await until(`Boolean(document.querySelector('dialog form:not([hidden])'))`)
  await key('Escape', 27)
  await until(`document.querySelector('dialog h2').textContent.includes('Descartar')`)
  await button('Descartar cambios')
  await closed()
  assert.equal(await evaluate(`window.profileModalTest.saves.length`), 0)
  await open('.reader-story')
  assert.equal(await evaluate(`document.querySelector('dialog textarea').value`), 'Historia guardada')
  await input('dialog textarea', 'x'.repeat(201))
  assert.equal(await evaluate(`document.querySelector('dialog button[type=submit]').disabled && document.querySelector('#biography-count').textContent.includes('201/200')`), true)
  await input('dialog textarea', 'Nueva historia guardada')
  await evaluate(`window.profileModalTest.failSave=true`)
  await button('Guardar')
  await until(`Boolean(document.querySelector('dialog [role=alert]'))`)
  assert.equal(await evaluate(`document.querySelector('dialog textarea').value`), 'Nueva historia guardada')
  await evaluate(`window.profileModalTest.failSave=false;window.profileModalTest.delay=2000`)
  await button('Guardar')
  assert.equal(await evaluate(`document.querySelector('.reader-modal-close').disabled && document.querySelector('dialog button[type=submit]').textContent.includes('Guardando')`), true)
  await key('Escape', 27)
  assert.equal(await evaluate(`Boolean(document.querySelector('dialog[open]'))`), true, 'Cannot close a pending save')
  await closed()
  assert.equal(await evaluate(`document.querySelector('.reader-biography').textContent`), 'Nueva historia guardada')
  await evaluate(`window.profileModalTest.delay=50`)
  console.log('PASS: stable cards, focus trap/restore, inert background, dirty confirmation, validation, save/error/busy states')

  // Catalog errors remain inside the modal and support retry.
  await evaluate(`window.profileModalTest.failCatalog=true`)
  await open('.reader-favorite-genres')
  await until(`Boolean(document.querySelector('dialog [role=alert]'))`)
  assert.equal(await evaluate(`document.querySelector('dialog button[type=submit]').disabled`), true)
  await evaluate(`window.profileModalTest.failCatalog=false`)
  await button('Reintentar')
  await until(`document.querySelectorAll('dialog input[type=checkbox]').length===6`)
  assert.equal(await evaluate(`document.querySelectorAll('dialog .reader-selected-genres li').length===5 && document.querySelectorAll('dialog input[type=checkbox]:disabled').length===1`), true)
  await evaluate(`document.querySelector('dialog .reader-selected-genres button').click()`)
  await pause(30)
  await evaluate(`document.querySelectorAll('dialog input[type=checkbox]')[0].click()`)
  await button('Guardar')
  await closed()
  assert.deepEqual(await evaluate(`Object.keys(window.profileModalTest.saves.at(-1))`), ['genre_ids'])

  await open('.reader-tastes')
  await until(`document.querySelectorAll('dialog input[type=checkbox]').length===6`)
  await evaluate(`document.querySelector('dialog input[type=checkbox]:not(:checked)').click()`)
  await button('Guardar')
  await closed()
  assert.deepEqual(await evaluate(`Object.keys(window.profileModalTest.saves.at(-1))`), ['trope_ids'])
  assert.equal(await evaluate(`document.querySelectorAll('.reader-tastes .reader-taste-tags li').length`), 6)

  await open('.reader-reading-tastes')
  await until(`document.querySelectorAll('dialog .reader-intensity-item').length===5`)
  assert.equal(await evaluate(`document.querySelector('dialog select').disabled && !document.querySelector('dialog').textContent.includes('Otros intereses')`), true)
  await evaluate(`document.querySelector('dialog input[aria-label^="Romance: 5 "]').click();document.querySelector('dialog .reader-feature-choice').click()`)
  await button('Guardar')
  await closed()
  assert.deepEqual(await evaluate(`Object.keys(window.profileModalTest.saves.at(-1)).sort()`), ['featured_category_id', 'intensities'])
  assert.equal(await evaluate(`document.querySelectorAll('.reader-taste-highlight .reader-intensity').length===1 && document.querySelector('.reader-reading-tastes h2').textContent.includes('Romance')`), true)
  console.log('PASS: all four existing save contracts, catalog retry, genre limit, trope selection, five ratings and single featured taste')

  await open('.reader-story')
  await evaluate(`document.querySelector('.reader-modal-close').click()`)
  await closed()
  await open('.reader-story')
  await key('Escape', 27)
  await closed()
  await open('.reader-story')
  await input('dialog textarea', 'Cambios para probar el overlay')
  const backdropPoint = await evaluate(`(() => {const r=document.querySelector('dialog').getBoundingClientRect();return{x:r.left-4,y:r.top+10}})()`)
  for (const type of ['mousePressed', 'mouseReleased']) await send('Input.dispatchMouseEvent', { type, ...backdropPoint, button: 'left', clickCount: 1 })
  await until(`document.querySelector('dialog h2').textContent.includes('Descartar')`)
  await button('Descartar cambios')
  await closed()

  const sections = ['.reader-story', '.reader-favorite-genres', '.reader-tastes', '.reader-reading-tastes']
  for (const theme of ['lavanda', 'otono', 'invierno', 'dark', 'bosque', 'rosa-antiguo', 'dark-rosado', 'dark-blood', 'dark-dorado']) {
    await evaluate(`import('/src/theme/themes.js').then(module=>module.applyTheme('${theme}'))`)
    for (const width of [1440, 768, 390, 320]) {
      await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: width < 500 })
      for (const section of sections) {
        await open(section)
        assert.equal(await evaluate(`(() => {const d=document.querySelector('dialog');const r=d.getBoundingClientRect();return r.width<=700&&r.left>=0&&r.right<=innerWidth&&r.height<=innerHeight&&document.documentElement.scrollWidth<=innerWidth&&d.scrollWidth<=d.clientWidth+1&&getComputedStyle(d).backgroundColor===getComputedStyle(document.querySelector('.reader-modal-footer')).backgroundColor})()`), true, `Modal bounds/theme at ${theme}, ${width}`)
        await button('Cancelar')
        await closed()
      }
    }
  }
  console.log('PASS: X/Escape/backdrop close rules; all four modals in nine themes at desktop/tablet/mobile widths, without card movement or horizontal overflow')
  await send('Emulation.setDeviceMetricsOverride', { width: 768, height: 380, deviceScaleFactor: 1, mobile: false })
  await open('.reader-reading-tastes')
  assert.equal(await evaluate(`(() => {const r=document.querySelector('dialog').getBoundingClientRect();const fields=document.querySelector('.reader-modal-fields');return r.height<=innerHeight&&fields.scrollHeight>fields.clientHeight&&fields.clientHeight>0&&document.querySelector('.reader-modal-footer').getBoundingClientRect().bottom<=innerHeight})()`), true, 'Short viewports must scroll only the modal body and keep footer visible')
  await button('Cancelar')
  await closed()
  await send('Page.navigate', { url: `${fixture}?public` })
  await until(`document.querySelectorAll('.reader-about-grid>.reader-personal-card').length===4`)
  assert.equal(await evaluate(`!document.querySelector('.reader-about-grid .reader-edit-button,dialog[open]')`), true)
  console.log('PASS: community profile remains read-only')
} finally {
  ws.close()
  await fetch(`${cdp}/json/close/${target.id}`)
}
