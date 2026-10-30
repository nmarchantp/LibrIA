import assert from 'node:assert/strict'
const cdp = process.env.CDP_URL || 'http://127.0.0.1:9224'
const app = process.env.VITE_URL || 'http://127.0.0.1:5173'
const target = await (await fetch(`${cdp}/json/new?about:blank`, { method: 'PUT' })).json()
const socket = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
let sequence = 0
const pending = new Map()
socket.onmessage = event => { const data = JSON.parse(event.data); if (pending.has(data.id)) { pending.get(data.id)(data); pending.delete(data.id) } }
const send = (method, params = {}) => new Promise(resolve => { pending.set(++sequence, resolve); socket.send(JSON.stringify({ id: sequence, method, params })) })
async function evaluate(expression) { const value = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }); if (value.result?.exceptionDetails) throw Error(JSON.stringify(value.result.exceptionDetails)); return value.result.result.value }
async function until(expression) { for (let n = 0; n < 100; n++) { if (await evaluate(expression)) return; await new Promise(r => setTimeout(r, 50)) } throw Error('Timed out: '+expression) }
async function setValue(selector, value) { await evaluate(`(() => { const input=document.querySelector(${JSON.stringify(selector)}); Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input),'value').set.call(input,${JSON.stringify(value)});input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true})); })()`); await new Promise(r => setTimeout(r, 50)) }
try {
  await send('Page.navigate', { url: `${app}/tests/fixtures/account-management.html` })
  await until(`Boolean(document.querySelector('.account-management textarea'))`)
  assert.equal(await evaluate(`document.querySelectorAll('.account-management input[readonly]').length`), 2)
  await setValue('.account-management textarea', '📚'.repeat(71))
  assert.equal(await evaluate(`document.querySelector('#account-bio-count').textContent`), '71/70 caracteres')
  assert.equal(await evaluate(`document.querySelector('.account-management button').disabled`), true)
  await setValue('.account-management textarea', '📚'.repeat(70))
  await evaluate(`document.querySelector('.account-management form').requestSubmit()`)
  await until(`window.accountTest.calls.some(c=>c.method==='PATCH'&&c.path==='/accounts/me')`)
  assert.equal(await evaluate(`Array.from(window.accountTest.calls.find(c=>c.method==='PATCH').body.biography).length`), 70)
  await until(`document.querySelector('.account-management [role=status]')?.textContent.includes('Perfil actualizado')`)
  await evaluate(`document.querySelector('.admin-accounts .admin-profile-list button').click()`)
  await until(`Boolean(document.querySelector('.admin-accounts fieldset'))`)
  assert.equal(await evaluate(`document.querySelector('.admin-accounts fieldset').disabled`), true)
  await setValue('.admin-accounts textarea', 'Motivo administrativo obligatorio')
  assert.equal(await evaluate(`document.querySelector('.admin-accounts fieldset').disabled`), false)
  await evaluate(`document.querySelector('.admin-accounts fieldset button').click()`)
  await until(`window.accountTest.calls.some(c=>c.path.endsWith('/suspension'))`)
  assert.equal(await evaluate(`window.accountTest.calls.find(c=>c.path.endsWith('/suspension')).body.reason`), 'Motivo administrativo obligatorio')
  for (const width of [1280, 390, 320]) {
    await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: width < 500 })
    assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth`), true, `Account layout at ${width}`)
  }
  await send('Page.navigate', { url: `${app}/tests/fixtures/account-management.html?recovery&deadline=2026-11-29T12:00:00Z` })
  await until(`Boolean(document.querySelector('.auth-card select'))`)
  assert.equal(await evaluate(`document.querySelector('select').value`), 'recover_deletion')
  await setValue('.auth-card input[name=token]', 'x'.repeat(43))
  await evaluate(`document.querySelectorAll('.auth-card form')[1].requestSubmit()`)
  await until(`document.querySelector('[role=status]')?.textContent.includes('suspensión administrativa continúa')`)
  assert.equal(await evaluate(`!document.querySelector('[role=status]').textContent.includes('Ya puedes ingresar')`), true)
  console.log('PASS: read-only username/role, Unicode biography limit, save contract, admin reason, responsive layout, deletion recovery and retained suspension')
} finally { socket.close(); await fetch(`${cdp}/json/close/${target.id}`) }
