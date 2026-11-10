import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { mkdir, writeFile } from 'node:fs/promises'
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
async function input(value){await evaluate(`(()=>{const input=document.querySelector('#reading-challenge-target');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(value)});input.dispatchEvent(new Event('input',{bubbles:true}))})()`)}
async function edit(){await evaluate(`document.querySelector('[aria-label="Editar meta anual"]').click()`);await until(`Boolean(document.querySelector('.reader-profile-modal[open]'))`)}
async function save(){await evaluate(`document.querySelector('.reader-profile-modal form').requestSubmit()`)}
try{
  await send('Runtime.enable')
  await send('Emulation.setDeviceMetricsOverride',{width:1536,height:1100,deviceScaleFactor:1,mobile:false})
  await send('Page.navigate',{url:`${app}/tests/fixtures/mural.html?count=8&role=lector&profile_tab=about`})
  await until(`Boolean(document.querySelector('.reading-challenge-action'))`)
  await until(`document.querySelector('.reading-challenge-art.is-start')?.naturalWidth>0`)
  assert.match(await evaluate(`document.querySelector('.reading-challenge').textContent`),/Cada gran aventura/)
  await evaluate(`document.querySelector('.reading-challenge-action').click()`)
  await until(`Boolean(document.querySelector('.reader-profile-modal[open]'))`)
  await evaluate(`import('/src/theme/themes.js').then(module=>module.applyTheme('dark-dorado'))`)
  await evaluate(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`)
  {
    const clip=await evaluate(`(()=>{const rect=document.querySelector('.reading-challenge-modal').getBoundingClientRect();return {x:rect.left+scrollX,y:rect.top+scrollY,width:rect.width,height:rect.height,scale:1}})()`)
    const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip})
    const directory=new URL('../../../artifacts/reading-challenge/',import.meta.url)
    await mkdir(directory,{recursive:true});await writeFile(new URL('modal.png',directory),Buffer.from(screenshot.result.data,'base64'))
  }
  assert.equal(await evaluate(`document.querySelectorAll('.reading-challenge-suggestions button').length`),5)
  await input('0')
  assert.equal(await evaluate(`document.querySelector('.reader-profile-modal button[type="submit"]').disabled`),true)
  await input('1.5')
  assert.equal(await evaluate(`document.querySelector('.reader-profile-modal button[type="submit"]').disabled`),true)
  await evaluate(`document.querySelector('.reading-challenge-suggestions button:nth-child(2)').click()`)
  await save()
  await until(`Boolean(document.querySelector('.reading-challenge-progress'))&&!document.querySelector('.reader-profile-modal')`)
  assert.match(await evaluate(`document.querySelector('.reading-challenge-count').textContent`),/0 de 12 libros/)
  await evaluate(`window.challengeTest.finished_books=8;dispatchEvent(new Event('libria:book-activity-changed'))`)
  await until(`document.querySelector('.reading-challenge-percentage').textContent==='67 % completado'`)
  await until(`document.querySelector('.reading-challenge-art.is-progress')?.naturalWidth>0`)
  await evaluate(`import('/src/theme/themes.js').then(module=>module.applyTheme('dark-dorado'))`)
  await evaluate(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`)
  {
    const clip=await evaluate(`(()=>{const rect=document.querySelector('.reading-challenge').getBoundingClientRect();return {x:rect.left+scrollX,y:rect.top+scrollY,width:rect.width,height:rect.height,scale:1}})()`)
    const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip})
    const directory=new URL('../../../artifacts/reading-challenge/',import.meta.url)
    await mkdir(directory,{recursive:true});await writeFile(new URL('progress.png',directory),Buffer.from(screenshot.result.data,'base64'))
  }
  for(const width of [1536,768,390,320]){
    await send('Emulation.setDeviceMetricsOverride',{width,height:1100,deviceScaleFactor:1,mobile:width<500})
    for(const theme of ['lavanda','otono','invierno','bosque','rosa-antiguo','dark','dark-rosado','dark-blood','dark-dorado']){
      await evaluate(`import('/src/theme/themes.js').then(module=>module.applyTheme('${theme}'))`)
      assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth&&document.querySelector('.reading-challenge').scrollWidth<=document.querySelector('.reading-challenge').clientWidth+1`),true,`${width}/${theme}: card fits`)
    }
    await edit()
    assert.equal(await evaluate(`document.querySelector('.reader-profile-modal').scrollWidth<=innerWidth`),true,`${width}: modal fits`)
    await evaluate(`document.querySelector('.reader-modal-close').click()`)
  }
  await edit();await input('8');await save()
  await until(`Boolean(document.querySelector('.reading-challenge-completed'))`)
  await until(`document.querySelector('.reading-challenge-art.is-complete')?.naturalWidth>0&&document.querySelector('.reading-challenge-completed img')?.naturalWidth>0`)
  assert.match(await evaluate(`document.querySelector('.reading-challenge-result').textContent`),/Reto completado/)
  await evaluate(`window.challengeTest.finished_books=15;dispatchEvent(new Event('libria:book-activity-changed'))`)
  await until(`document.querySelector('.reading-challenge-count').textContent==='15 de 8 libros'`)
  for(const width of [1536,390,320]){
    await send('Emulation.setDeviceMetricsOverride',{width,height:1100,deviceScaleFactor:1,mobile:width<500})
    for(const theme of ['lavanda','otono','invierno','bosque','rosa-antiguo','dark','dark-rosado','dark-blood','dark-dorado']){
      await evaluate(`import('/src/theme/themes.js').then(module=>module.applyTheme('${theme}'))`)
      assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth&&document.querySelector('.reading-challenge').scrollWidth<=document.querySelector('.reading-challenge').clientWidth+1`),true,`${width}/${theme}: completed card fits`)
    }
    if(width===1536){
      const clip=await evaluate(`(()=>{const rect=document.querySelector('.reading-challenge').getBoundingClientRect();return {x:rect.left+scrollX,y:rect.top+scrollY,width:rect.width,height:rect.height,scale:1}})()`)
      await evaluate(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`)
      const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip})
      const directory=new URL('../../../artifacts/reading-challenge/',import.meta.url)
      await mkdir(directory,{recursive:true});await writeFile(new URL('completed.png',directory),Buffer.from(screenshot.result.data,'base64'))
    }
  }
  assert.equal(await evaluate(`document.querySelector('.reading-challenge-progress progress').value`),100)
  await edit();await input('20');await save()
  await until(`!document.querySelector('.reading-challenge-completed')`)
  assert.equal(await evaluate(`document.querySelector('.reading-challenge-art.is-complete')`),null,'Completion artwork is removed when the target increases')
  assert.equal(await evaluate(`document.querySelector('.reading-challenge-progress progress').value`),75)
  await edit();await input('30');await evaluate(`window.challengeTest.failSave=true`);await save()
  await until(`Boolean(document.querySelector('.reader-profile-modal [role="alert"]'))`)
  assert.equal(await evaluate(`document.querySelector('#reading-challenge-target').value`),'30')
  await evaluate(`window.challengeTest.failSave=false`);await save()
  await until(`!document.querySelector('.reader-profile-modal')`)
  assert.match(await evaluate(`document.querySelector('.reading-challenge-count').textContent`),/15 de 30 libros/)
  await evaluate(`window.challengeTest.finished_books=0;dispatchEvent(new Event('libria:book-activity-changed'))`)
  await until(`document.querySelector('.reading-challenge-progress progress').value===0`)
  assert.deepEqual(errors,[])
  console.log('PASS: empty/create/edit/custom target, validation, real-response refresh, exact/exceeded/recalculated goal, errors preserve input, nine themes and four widths, accessible modal')
}finally{ws.close();await fetch(`${cdp}/json/close/${target.id}`)}
