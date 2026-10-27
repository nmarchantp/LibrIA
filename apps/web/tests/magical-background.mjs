// Isolated browser fixture and real layout/providers; no backend writes.
import assert from 'node:assert/strict'
const cdp = process.env.CDP_URL || 'http://127.0.0.1:9224'
const fixture = `${process.env.VITE_URL || 'http://127.0.0.1:5173'}/tests/fixtures/profile-modals.html`
const key = 'libriaverse-magical-background'
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
async function navigate(path) {
  await evaluate(`history.pushState({},'',${JSON.stringify(path)});dispatchEvent(new PopStateEvent('popstate'))`)
  await pause(80)
}
try {
  await send('Page.enable')
  const init = await send('Page.addScriptToEvaluateOnNewDocument', { source: `localStorage.removeItem('${key}')` })
  await send('Page.navigate', { url: fixture })
  await until(`document.querySelectorAll('.profile-starfield').length===1`)
  await send('Page.removeScriptToEvaluateOnNewDocument', { identifier: init.result.identifier })
  assert.equal(await evaluate(`localStorage.getItem('${key}')`), 'true')
  assert.deepEqual(await evaluate(`[...document.querySelectorAll('.profile-starfield-layer')].map(e=>{const s=getComputedStyle(e);return [s.opacity,s.animationDuration,s.backgroundSize.split(',').every(size=>size.trim()==='600px 600px')]})`), [['0.28', '50s', true], ['0.4', '100s', true], ['0.55', '150s', true]])
  assert.equal(await evaluate(`(()=>{const rule=[...document.styleSheets].flatMap(s=>{try{return [...s.cssRules]}catch{return []}}).find(r=>r.type===CSSRule.KEYFRAMES_RULE&&r.name==='profile-starfield-rise');return rule.cssRules[0].style.transform==='translateY(-600px)'&&rule.cssRules[1].style.transform==='translateY(0px)'})()`), true, 'Keep the approved downward direction')
  await evaluate(`window.__background=document.querySelector('.profile-starfield');window.__starAnimation=document.querySelector('.profile-starfield-layer').getAnimations()[0]`)
  for (const path of ['/', '/profile', '/profile?tab=library', '/profile?tab=analysis', '/profile?tab=activity', '/books', '/events', '/recommendations', '/messages', '/notifications', '/settings?tab=personalization', '/profiles/fixture']) {
    await navigate(path)
    assert.equal(await evaluate(`document.querySelectorAll('.profile-starfield').length===1&&document.querySelector('.profile-starfield')===window.__background`), true, path)
    assert.equal(await evaluate(`document.querySelector('.profile-starfield-layer').getAnimations()[0]===window.__starAnimation`), true, 'Navigation must not restart animation')
  }
  console.log('PASS default enabled, one persistent instance and uninterrupted animations across twelve authenticated views')

  const ids = await evaluate(`import('/src/theme/themes.js').then(m=>m.themes.map(t=>t.id))`)
  await navigate('/settings?tab=personalization')
  for (const id of ids) {
    await evaluate(`document.querySelector('[data-theme-option="${id}"]').click()`)
    const theme = await evaluate(`localStorage.getItem('libria_theme')`)
    await evaluate(`document.querySelector('.visual-effects-switch input').click()`)
    await until(`document.querySelectorAll('.profile-starfield').length===0&&localStorage.getItem('${key}')==='false'`)
    assert.equal(await evaluate(`document.querySelector('.visual-effects-switch input').checked`), false)
    assert.equal(await evaluate(`localStorage.getItem('libria_theme')`), theme)
    assert.equal(await evaluate(`document.getAnimations().some(a=>a.animationName==='profile-starfield-rise')`), false)
    await send('Page.navigate', { url: fixture })
    await until(`Boolean(document.querySelector('.reader-profile'))`)
    assert.equal(await evaluate(`document.querySelectorAll('.profile-starfield').length`), 0)
    assert.equal(await evaluate(`document.documentElement.dataset.theme`), id)
    await navigate('/settings?tab=personalization')
    await evaluate(`document.querySelector('.visual-effects-switch input').click()`)
    await until(`document.querySelectorAll('.profile-starfield').length===1&&localStorage.getItem('${key}')==='true'`)
    await send('Page.navigate', { url: fixture })
    await until(`document.querySelectorAll('.profile-starfield').length===1`)
    await navigate('/settings?tab=personalization')
  }
  console.log('PASS independent theme/preference storage, immediate toggle, full unmount and enabled/disabled persistence in nine themes')

  for (const width of [1440, 768, 390, 320]) {
    await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: width < 700 })
    assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth`), true)
    assert.equal(await evaluate(`getComputedStyle(document.querySelector('.profile-starfield')).pointerEvents`), 'none')
    await evaluate(`document.querySelector('.visual-effects-switch input').scrollIntoView({block:'center'});document.querySelector('.visual-effects-switch input').focus()`)
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: ' ', code: 'Space', windowsVirtualKeyCode: 32 })
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: ' ', code: 'Space', windowsVirtualKeyCode: 32 })
    await until(`document.querySelectorAll('.profile-starfield').length===0`)
    await evaluate(`document.querySelector('.visual-effects-switch input').click()`)
    await until(`document.querySelectorAll('.profile-starfield').length===1`)
  }
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
  assert.equal(await evaluate(`[...document.querySelectorAll('.profile-starfield-layer')].every(e=>getComputedStyle(e).animationName==='none')`), true)
  await navigate('/profile')
  await evaluate(`document.querySelector('.reader-edit-button').click()`)
  await until(`Boolean(document.querySelector('dialog[open]'))`)
  await evaluate(`document.querySelector('dialog button').click()`)
  await evaluate(`document.querySelector('.logout-button').click()`)
  await until(`location.pathname==='/login'`)
  assert.equal(await evaluate(`document.querySelectorAll('.profile-starfield').length`), 0)
  console.log('PASS keyboard switch, mobile/tablet/desktop, reduced motion, editor interaction and exclusion from login')
} finally {
  await send('Emulation.setEmulatedMedia', { features: [] })
  ws.close()
  await fetch(`${cdp}/json/close/${target.id}`)
}
