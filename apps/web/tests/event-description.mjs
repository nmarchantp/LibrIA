import assert from 'node:assert/strict'
import {mkdir,writeFile} from 'node:fs/promises'
import { readFileSync } from 'node:fs'
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
try{
  await send('Runtime.enable')
  await send('Emulation.setDeviceMetricsOverride',{width:1536,height:1100,deviceScaleFactor:1,mobile:false})
  await send('Page.navigate',{url:`${app}/tests/fixtures/mural.html?count=6&description=1&role=admin`})
  await until(`Boolean(document.querySelector('.mural-audiences'))`)
  await evaluate(`document.querySelectorAll('.mural-audiences button')[2].click()`)
  await until(`document.querySelectorAll('.mural-event-content').length===6`)
  const first=`document.querySelector('.mural-event-content')`
  await until(`${first}.querySelector('.mural-event-description-toggle').getAttribute('aria-expanded')==='false'`)
  assert.equal(await evaluate(`getComputedStyle(${first}.querySelector('.mural-event-description-toggle')).visibility`),'visible')
  assert.equal(await evaluate(`document.querySelectorAll('.mural-event-content')[1].querySelector('.mural-event-description-toggle')===null`),true,'Short text has no expansion control')
  assert.equal(await evaluate(`${first}.querySelector('.mural-event-description-text strong').textContent`),'Una invitaci\u00f3n literaria')
  assert.equal(await evaluate(`${first}.querySelector('.mural-event-description-text em').textContent`),'historias y encuentros')
  const content=await evaluate(`${first}.querySelector('.mural-event-description-text').textContent`)
  const initial=await evaluate(`${first}.getBoundingClientRect().height`)
  await evaluate(`${first}.querySelector('.mural-event-description-toggle').click()`)
  await until(`${first}.querySelector('.mural-event-description-toggle').getAttribute('aria-expanded')==='true'`)
  assert.ok(await evaluate(`${first}.getBoundingClientRect().height>${initial}+100`),'Expanded text grows the layout')
  assert.equal(await evaluate(`${first}.querySelector('.mural-event-description-text').textContent`),content)
  assert.equal(await evaluate(`(()=>{const root=${first};return root.querySelector('.post-gallery-editorial').getBoundingClientRect().top>=root.querySelector('.mural-event-description').getBoundingClientRect().bottom})()`),true,'Expanded text never overlaps the gallery')
  await evaluate(`${first}.querySelector('.mural-event-description-toggle').click()`)
  await until(`${first}.querySelector('.mural-event-description-toggle').getAttribute('aria-expanded')==='false'`)
  assert.ok(await evaluate(`Math.abs(${first}.getBoundingClientRect().height-${initial})<1`),'Collapse restores the original height')
  for(const theme of ['lavanda','otono','invierno','bosque','rosa-antiguo','dark','dark-rosado','dark-blood','dark-dorado']){
    await evaluate(`import('/src/theme/themes.js').then(module=>module.applyTheme('${theme}'))`)
    for(const width of [1536,1100,768,390,320]){
      await send('Emulation.setDeviceMetricsOverride',{width,height:1100,deviceScaleFactor:1,mobile:width<500})
      await until(`(()=>{const root=document.querySelector('.mural-event-content'),text=root.querySelector('.mural-event-description-text'),height=text.getBoundingClientRect().height,lineHeight=parseFloat(getComputedStyle(text.querySelector('.post-text')).lineHeight),lines=parseInt(getComputedStyle(root).getPropertyValue('--event-description-lines'));return lines>=4&&lines<=6&&Math.abs(height-lines*lineHeight)<1})()`)
      assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth`),true,`${theme}/${width}: no overflow`)
      assert.equal(await evaluate(`Array.from(document.querySelectorAll('.mural-event-content')).every(root=>{const gallery=root.querySelector('.post-gallery-editorial');if(!gallery)return true;const image=gallery.querySelector('.post-gallery-tile').getBoundingClientRect(),title=root.querySelector('h2').getBoundingClientRect(),text=root.querySelector('.mural-event-description').getBoundingClientRect();return Math.abs(image.left-title.left)<1&&Math.abs(image.left-text.left)<1&&Math.abs(gallery.getBoundingClientRect().top-text.bottom-12)<1})`),true,'Gallery starts directly below text in the central column')
      assert.equal(await evaluate(`Array.from(document.querySelectorAll('.mural-event-content')).every(root=>{const header=root.querySelector('.mural-event-heading').getBoundingClientRect(),meta=root.querySelector('.mural-event-heading-metadata').getBoundingClientRect(),description=root.querySelector('.mural-event-description').getBoundingClientRect();return meta.bottom<=header.bottom+1&&description.top>=header.bottom-1})`),true,'Place and organizer stay in the heading above the description')
      assert.equal(await evaluate(`Array.from(document.querySelectorAll('.mural-publication-event .mural-publication-editorial.has-related-book')).every(layout=>{const book=layout.querySelector('.mural-related-book').getBoundingClientRect(),main=layout.querySelector('.mural-publication-content').getBoundingClientRect(),bounds=layout.getBoundingClientRect();return book.top>=main.bottom-1||(book.width<=193.5&&main.width>book.width&&Math.abs(book.right-bounds.right)<1)})`),true,'Related book reserves only its required width at the right edge')
      assert.equal(await evaluate(`Array.from(document.querySelectorAll('.mural-event-content .post-gallery-editorial')).every(gallery=>{const tiles=Array.from(gallery.children,node=>node.getBoundingClientRect());return tiles.length<=4&&tiles.every(tile=>tile.height<=180.5&&Math.abs(tile.top-tiles[0].top)<1)})`),true,'Gallery remains one compact row')
      if(theme==='dark-dorado'&&width===1536){
        const output=new URL('../../../artifacts/event-description/',import.meta.url);await mkdir(output,{recursive:true})
        const clip=await evaluate(`(()=>{const r=document.querySelector('.mural-publication-event').getBoundingClientRect();return {x:r.left+scrollX,y:r.top+scrollY,width:r.width,height:r.height,scale:1}})()`)
        const screenshot=await send('Page.captureScreenshot',{format:'png',clip,captureBeyondViewport:true})
        await writeFile(new URL('event-layout.png',output),Buffer.from(screenshot.result.data,'base64'))
      }

    }
  }
  await send('Emulation.setDeviceMetricsOverride',{width:1536,height:1100,deviceScaleFactor:1,mobile:false})
  await until(`document.querySelectorAll('.mural-event-content')[1].querySelector('.mural-event-description-toggle')===null`)
  await evaluate(`document.querySelector('.mural-publication-event .event-edit-button').click()`)
  await until(`Boolean(document.querySelector('.content-management-dialog textarea'))`)
  await evaluate(`(()=>{const input=document.querySelector('.content-management-dialog textarea');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(input,'Texto actualizado y breve.');input.dispatchEvent(new Event('input',{bubbles:true}))})()`)
  await evaluate(`document.querySelector('.content-management-dialog .post-composer').requestSubmit()`)
  await until(`!document.querySelector('.content-management-dialog')&&document.querySelector('.mural-event-description-text').textContent==='Texto actualizado y breve.'`)
  await until(`document.querySelector('.mural-event-content').querySelector('.mural-event-description-toggle')===null`)
  await evaluate(`document.querySelectorAll('.mural-audiences button')[3].click()`)
  await until(`Boolean(document.querySelector('.mural-publication'))`)
  assert.equal(await evaluate(`Boolean(document.querySelector('.mural-event-description-toggle'))`),false,'Other publication types stay unchanged')
  assert.deepEqual(errors,[])
  console.log('PASS: real overflow, short text, expansion/collapse, formatting, gallery flow, no-photo events and nine responsive themes')
}finally{ws.close();await fetch(`${cdp}/json/close/${target.id}`)}
