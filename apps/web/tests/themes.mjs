// Real React/CSS in the isolated browser fixture; never writes to the backend.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const cdp = process.env.CDP_URL || 'http://127.0.0.1:9224'
const fixture = `${process.env.VITE_URL || 'http://127.0.0.1:5173'}/tests/fixtures/profile-modals.html`
const baseline = JSON.parse(await readFile(new URL('./fixtures/original-theme-appearance.json', import.meta.url), 'utf8'))
const target = await (await fetch(`${cdp}/json/new?about:blank`, { method: 'PUT' })).json()
const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject })
let sequence = 0
const pending = new Map()
const browserErrors = []
ws.onmessage = event => {
  const message = JSON.parse(event.data)
  if (message.method === 'Runtime.exceptionThrown') browserErrors.push(message.params.exceptionDetails)
  if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') browserErrors.push(message.params.args)
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
async function navigate(path) {
  await evaluate(`history.pushState({},'',${JSON.stringify(path)});window.dispatchEvent(new PopStateEvent('popstate'))`)
}
try {
  await send('Runtime.enable')
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  await send('Page.navigate', { url: fixture })
  await until(`Boolean(document.querySelector('.reader-profile'))`)
  await pause(250)
  for (const id of Object.keys(baseline)) {
    const actual = await evaluate(`(async()=>{
      const {applyTheme,themes}=await import('/src/theme/themes.js');applyTheme('${id}');
      const root=getComputedStyle(document.documentElement);
      const vars=Object.fromEntries([...root].filter(p=>p.startsWith('--')).sort().map(p=>[p,root.getPropertyValue(p).trim()]));
      const selectors=['.social-sidebar','.social-topbar','.header-greeting-title','.reader-personal-card','.reader-edit-button','.reader-taste-tags li','.message-envelope','.notification-bell'];
      const appearance=Object.fromEntries(selectors.map(s=>{const e=document.querySelector(s);if(!e)return [s,null];const c=getComputedStyle(e);return [s,Object.fromEntries(['color','backgroundColor','backgroundImage','borderColor','fill','stroke','boxShadow'].map(p=>[p,c[p]]))]}));
      const {getProfileBanner}=await import('/src/theme/profileBanners.js');
      return {colors:themes.find(t=>t.id==='${id}').colors,vars,colorScheme:root.colorScheme,appearance,banner:getProfileBanner('${id}')}
    })()`)
    for (const key of ['colors', 'vars', 'colorScheme', 'banner']) assert.deepEqual(actual[key], baseline[id][key], `${id}: ${key}`)
    for (const [selector, expected] of Object.entries(baseline[id].appearance)) {
      // SVGs paint with explicit fill/stroke, not their transitioning inherited
      // color/border-color. Compare the stable properties captured before edits.
      // The header was independently changed to transparent after this palette
      // baseline. Keep the palette comparison without undoing that approved UI.
      const stableExpected = expected && Object.fromEntries(Object.entries(expected).filter(([key]) => !(selector === '.social-topbar' && key === 'backgroundColor')))
      const properties = stableExpected && Object.fromEntries(Object.keys(stableExpected).map(key => [key, actual.appearance[selector]?.[key]]))
      assert.deepEqual(properties, stableExpected, `${id}: ${selector}`)
      if (selector === '.social-topbar') assert.equal(actual.appearance[selector].backgroundColor, 'rgba(0, 0, 0, 0)')
    }
  }
  console.log('PASS six original palettes: unchanged variables, component colors, shadows, color scheme and banner configuration')

  const ids = await evaluate(`import('/src/theme/themes.js').then(m=>m.themes.map(t=>t.id))`)
  assert.equal(ids.length, 9)
  assert.equal(new Set(ids).size, 9)
  for (const id of ids) {
    await navigate('/settings?tab=personalization')
    await until(`document.querySelectorAll('.theme-option').length===9`)
    assert.equal(await evaluate(`document.querySelectorAll('.theme-options').length===1&&!document.querySelector('.theme-group')`), true)
    assert.deepEqual(await evaluate(`[...document.querySelectorAll('.theme-option')].map(e=>e.dataset.themeOption)`), ids)
    await evaluate(`document.querySelector('[data-theme-option="${id}"]').click()`)
    await until(`document.documentElement.dataset.theme==='${id}'&&localStorage.getItem('libria_theme')==='${id}'`)
    assert.equal(await evaluate(`document.querySelectorAll('.theme-option[aria-pressed=true]').length`), 1)
    // Reload the isolated fixture document (its router rewrites the visible URL).
    await send('Page.navigate', { url: fixture })
    await until(`Boolean(document.querySelector('.reader-profile'))&&document.documentElement.dataset.theme==='${id}'`)
    const expected = await evaluate(`import('/src/theme/profileBanners.js').then(m=>m.getProfileBanner('${id}').src)`)
    await until(`(()=>{const img=document.querySelector('.reader-profile-cover img');return img?.getAttribute('src')==='${expected}'&&img.complete&&img.naturalWidth>0})()`)
  }
  console.log('PASS nine selections apply immediately, survive reload, preserve legacy IDs and load the expected banner')

  for (const id of ids.filter(id => id.startsWith('dark-'))) {
    await evaluate(`import('/src/theme/themes.js').then(m=>m.applyTheme('${id}'))`)
    const contrast = await evaluate(`(()=>{
      const pairs=[['ink','paper'],['ink','surface'],['muted','surface'],['primary','surface'],['accent-text','soft'],['on-primary','button-bg'],['error-text','error-bg'],['success-text','success-bg'],['warning-text','warning-bg'],['info-text','info-bg']];
      const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const ctx=canvas.getContext('2d');const probe=document.createElement('span');document.body.append(probe);
      const lum=role=>{probe.style.color='var(--'+role+')';ctx.fillStyle=getComputedStyle(probe).color;ctx.fillRect(0,0,1,1);const c=[...ctx.getImageData(0,0,1,1).data].slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return c[0]*.2126+c[1]*.7152+c[2]*.0722};
      const result=pairs.map(([fg,bg])=>{const a=lum(fg),b=lum(bg);return {pair:fg+'/'+bg,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)}});probe.remove();return result
    })()`)
    for (const { pair, ratio } of contrast) assert.ok(ratio >= 4.5, `${id} ${pair}: ${ratio.toFixed(2)}:1`)
    for (const path of ['/', '/books', '/events', '/recommendations', '/messages', '/notifications', '/settings', '/profile?tab=library', '/profile?tab=analysis']) {
      await navigate(path)
      await pause(80)
      assert.equal(await evaluate(`getComputedStyle(document.documentElement).colorScheme`), 'dark')
      assert.equal(await evaluate(`!!document.querySelector('main#main-content>*')`), true)
    }
    console.log(`PASS ${id}: ten text/control/status contrast pairs >= 4.5:1 and nine authenticated views render`)
  }
  await navigate('/settings?tab=personalization')
  await until(`document.querySelectorAll('.theme-option').length===9`)
  for (const [width, columns] of [[1440, 5], [768, 2], [600, 1], [390, 1], [320, 1]]) {
    await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: width < 700 })
    assert.equal(await evaluate(`getComputedStyle(document.querySelector('.theme-options')).gridTemplateColumns.split(' ').length`), columns)
    assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth`), true)
    assert.equal(await evaluate(`[...document.querySelectorAll('.theme-option')].every(e=>{const r=e.getBoundingClientRect(),s=e.querySelector('.theme-swatches'),c=s.getBoundingClientRect();return r.height>=60&&r.height<=70&&c.width===44&&c.height===44&&getComputedStyle(s).backgroundImage.startsWith('linear-gradient(')&&e.scrollWidth<=e.clientWidth})`), true)
  }
  console.log('PASS single circular selector, compact 68px rows and responsive 5/2/1 columns without overflow')
  assert.deepEqual(browserErrors, [], 'No console errors or uncaught browser exceptions')
} finally {
  ws.close()
  await fetch(`${cdp}/json/close/${target.id}`)
}
