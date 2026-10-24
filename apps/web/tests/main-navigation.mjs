// Uses the existing isolated frontend fixture and Chromium CDP; no backend writes.
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
  if (message.id && pending.has(message.id)) { pending.get(message.id)(message); pending.delete(message.id) }
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
  for (let n = 0; n < 100; n++) { if (await evaluate(expression)) return; await pause(50) }
  throw new Error(`Timed out: ${expression}`)
}
async function click(selector) { await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`); await pause(70) }
const labels = ['Mural', 'Mi perfil', 'Explorar libros', 'Eventos', 'Recomendaciones IA', 'Configuración']
async function checkNavigation() {
  assert.deepEqual(await evaluate(`[...document.querySelectorAll('#main-navigation>a')].map(a=>a.textContent.trim())`), labels)
  assert.equal(await evaluate(`document.querySelectorAll('.social-topbar').length===1 && document.querySelectorAll('a[aria-current=page]').length<=1`), true, 'Single header and active route')
  assert.equal(await evaluate(`!!document.querySelector('.sidebar-account .account-link') && !!document.querySelector('.sidebar-account .logout-button')`), true)
}
try {
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  await send('Page.navigate', { url: fixture })
  await until(`Boolean(document.querySelector('#main-navigation'))`)
  await evaluate(`document.fonts.ready.then(()=>true)`)
  await checkNavigation()
  assert.equal(await evaluate(`!document.querySelector('.navigation-tools')`), true, 'No privileged links for regular reader')
  for (const [path, label] of [['/messages', 'Mensajes'], ['/notifications', 'Notificaciones']]) {
    const selector = `.social-topbar a[href="${path}"]`
    assert.equal(await evaluate(`document.querySelector(${JSON.stringify(selector)}).getAttribute('aria-label')`), label)
    await click(selector)
    assert.equal(await evaluate(`location.pathname`), path)
    assert.equal(await evaluate(`document.querySelector(${JSON.stringify(selector)}).getAttribute('aria-current')`), 'page')
    assert.equal(await evaluate(`document.querySelectorAll('#main-navigation a.active').length`), 0)
    await checkNavigation()
  }
  await click('#main-navigation a[href="/profile"]')
  await until(`document.querySelectorAll('.reader-profile-tabs button').length===4`)
  assert.deepEqual(await evaluate(`[...document.querySelectorAll('.reader-profile-tabs button')].map(b=>b.textContent.trim())`), ['Sobre mí', 'Mi biblioteca', 'Mis análisis', 'Mi actividad'])
  await evaluate(`document.querySelectorAll('.reader-profile-tabs button')[1].click()`)
  await until(`Boolean(document.querySelector('.reader-library-filters'))`)
  assert.equal(await evaluate(`new URLSearchParams(location.search).get('tab')`), 'library')
  await evaluate(`document.querySelectorAll('.reader-profile-tabs button')[2].click()`)
  assert.equal(await evaluate(`new URLSearchParams(location.search).get('tab')`), 'analysis')
  await checkNavigation()
  console.log('PASS exact six-link sidebar, single active route, header shortcuts, all profile tabs and existing library/analysis access')

  await click('#main-navigation a[href="/settings"]')
  await until(`Boolean(document.querySelector('.settings-page .account-details'))`)
  assert.equal(await evaluate(`document.querySelector('#main-navigation a[href="/settings"]').getAttribute('aria-current')`), 'page')
  await click('.settings-navigation a[href="/settings?tab=personalization"]')
  await until(`document.querySelectorAll('.settings-page .theme-option').length===6`)
  assert.equal(await evaluate(`!document.querySelector('.settings-page .account-details')`), true)
  for (const legacy of ['account', 'personalization']) {
    await evaluate(`history.pushState({},'', '/profile?tab=${legacy}');window.dispatchEvent(new PopStateEvent('popstate'))`)
    await until(`location.pathname==='/settings'`)
    assert.equal(await evaluate(`new URLSearchParams(location.search).get('tab')`), legacy === 'personalization' ? 'personalization' : null)
  }
  await click('#main-navigation a[href="/profile"]')
  await until(`document.querySelectorAll('.reader-profile-tabs button').length===4`)
  console.log('PASS settings account/theme sections, profile tabs relocated without duplication, and legacy profile links redirect')

  for (const theme of ['lavanda', 'otono', 'invierno', 'dark', 'bosque', 'rosa-antiguo']) {
    await evaluate(`import('/src/theme/themes.js').then(module=>module.applyTheme('${theme}'))`)
    for (const width of [1440, 768, 390, 320]) {
      await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: width < 500 })
      assert.equal(await evaluate(`(() => {
        const header=document.querySelector('.social-topbar').getBoundingClientRect();
        const actions=[...document.querySelectorAll('.social-topbar>a,.social-topbar .global-header-actions>a')].map(a=>a.getBoundingClientRect());
        return document.documentElement.scrollWidth<=innerWidth&&actions.length===2&&actions.every(r=>r.top>=0&&r.right<=innerWidth&&r.width>=40&&r.height>=44)&&header.right>innerWidth-40;
      })()`), true, `Header overflow/placement at ${theme} ${width}`)
      if (width < 701) {
        await click('.mobile-nav-toggle')
        assert.equal(await evaluate(`document.querySelector('.mobile-nav-toggle').getAttribute('aria-expanded')==='true'&&document.querySelector('.sidebar-account .account-link').getClientRects().length>0`), true)
        await checkNavigation()
        await click('#main-navigation a[href="/profile"]')
        assert.equal(await evaluate(`document.querySelector('.mobile-nav-toggle').getAttribute('aria-expanded')`), 'false')
      }
    }
  }
  console.log('PASS header/sidebar across six palettes and desktop/tablet/mobile widths; mobile menu closes on navigation and retains user/logout block')

  // Existing conditional links move to the header without changing their guards.
  for (const options of ['?group', '?role=admin', '?role=admin&group']) {
    await send('Page.navigate', { url: fixture + options })
    await until(`Boolean(document.querySelector('.navigation-tools'))`)
    await checkNavigation()
    const expected = options.includes('admin') ? options.includes('group') ? 3 : 2 : 1
    assert.equal(await evaluate(`document.querySelectorAll('.navigation-tools-menu a').length`), expected)
    await send('Emulation.setDeviceMetricsOverride', { width: 320, height: 700, deviceScaleFactor: 1, mobile: true })
    await click('.navigation-tools summary')
    assert.equal(await evaluate(`(() => {const brand=document.querySelector('.brand-link').getBoundingClientRect();const toggle=document.querySelector('.mobile-nav-toggle').getBoundingClientRect();const header=document.querySelector('.global-header-actions').getBoundingClientRect();const menu=document.querySelector('.navigation-tools-menu').getBoundingClientRect();return brand.right<=toggle.left+1&&toggle.right<=header.left+1&&menu.left>=0&&menu.right<=innerWidth&&document.documentElement.scrollWidth<=innerWidth})()`), true, `Privileged mobile header at ${options}`)
    await evaluate(`document.querySelector('.navigation-tools summary').focus()`)
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
    assert.equal(await evaluate(`!document.querySelector('.navigation-tools').open`), true)
  }
  console.log('PASS existing Insights/admin permissions and links retained in header tools, including 320px layout and keyboard dismissal')

  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  const icon = await evaluate(`(() => {const r=document.querySelector('.social-topbar a[href="/messages"]').getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`)
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', ...icon })
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.social-topbar a[href="/messages"] [role=tooltip]')).visibility`), 'visible')
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 0, y: 0 })
  await evaluate(`document.querySelector('.social-topbar a[href="/messages"]').focus()`)
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  assert.equal(await evaluate(`document.activeElement.closest('.global-header-actions')!==null&&getComputedStyle(document.activeElement.querySelector('[role=tooltip]')).visibility==='visible'`), true)
  console.log('PASS accessible shortcut names and tooltip visibility with hover and keyboard focus')
} finally {
  ws.close()
  await fetch(`${cdp}/json/close/${target.id}`)
}
