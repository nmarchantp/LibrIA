import assert from 'node:assert/strict'

const cdp = process.env.CDP_URL || 'http://127.0.0.1:9224'
const app = process.env.APP_URL || 'http://127.0.0.1:5173'
const target = await (await fetch(`${cdp}/json/new?about:blank`, { method:'PUT' })).json()
const socket = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => { socket.onopen=resolve; socket.onerror=reject })
let sequence=0
const pending=new Map()
socket.onmessage=event=>{
  const message=JSON.parse(event.data)
  if (pending.has(message.id)) {
    const {resolve,reject}=pending.get(message.id)
    pending.delete(message.id)
    if(message.error) reject(Error(JSON.stringify(message.error)))
    else resolve(message.result)
  }
}
const send=(method,params={})=>new Promise((resolve,reject)=>{
  pending.set(++sequence,{resolve,reject})
  socket.send(JSON.stringify({id:sequence,method,params}))
})
async function evaluate(expression) {
  const result=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})
  if(result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails))
  return result.result.value
}
async function until(expression) {
  for(let attempt=0;attempt<100;attempt++) {
    if(await evaluate(expression)) return
    await new Promise(resolve=>setTimeout(resolve,50))
  }
  throw Error(`Timed out: ${expression}`)
}
const click = async selector => {await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`)};
const fill = async (selector,value) => {await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el),'value').set.call(el,${JSON.stringify(value)});el.dispatchEvent(new Event('input',{bubbles:true}));})()`)};
try {
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 await send('Page.navigate',{url:`${app}/tests/fixtures/profile-modals.html`});
 await until(`Boolean(document.querySelector('.reader-literary-crush'))`);
 await evaluate(`(()=>{const original=window.fetch;window.fetch=(url,opts)=>{const path=String(url);if(path.includes('/characters'))return Promise.resolve(new Response(JSON.stringify({items:[{id:'character-one',name:'Rhysand',image_url:'/images/characters/rhysand-v1.webp'},{id:'character-two',name:'Feyre',image_url:'/images/characters/feyre-v1.webp'}]}),{headers:{'Content-Type':'application/json'}}));if(path.includes('/books?')){window.lastBookQuery=path;return Promise.resolve(new Response(JSON.stringify({items:[1,2,3,4,5].map(n=>({id:'book-'+n,volumeInfo:{title:'Libro '+n,authors:['Autora']}}))}),{headers:{'Content-Type':'application/json'}}));}return original(url,opts)}})()`);
 await click('.reader-about-edit-toggle');
 await click('[aria-label="Editar Mi crush literario"]');
 await until(`Boolean(document.querySelector('dialog[open]'))`);
 assert.equal(await evaluate(`Boolean(document.querySelector('dialog input[type="url"]'))`),false);
 await fill('dialog input[type="search"]','Libro');
 await until(`document.querySelectorAll('.literary-crush-book-results button').length===5`);
 assert.ok(await evaluate(`window.lastBookQuery.includes('local_only=true')`));
 await click('.literary-crush-book-results button');
 await until(`document.querySelectorAll('.literary-character-picker input').length===2`);
 await evaluate(`Promise.all([...document.querySelectorAll('.literary-character-picker img')].map(image=>image.decode()))`);
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:false});
 assert.ok(await evaluate(`document.documentElement.scrollWidth<=innerWidth+1 && document.querySelector('dialog').scrollWidth<=document.querySelector('dialog').clientWidth+1`),'Portrait picker fits mobile');
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 const screenshot=await send('Page.captureScreenshot',{format:'png'});
 await (await import('node:fs/promises')).writeFile(new URL('../../../artifacts/profile-character-picker.png',import.meta.url),Buffer.from(screenshot.data,'base64'));
 assert.equal(await evaluate(`document.querySelector('dialog button[type="submit"]').disabled`),true);
 await click('.literary-character-picker input');
 await fill('dialog textarea','Lealtad y valentía.');
 await click('dialog button[type="submit"]');
 await until(`!document.querySelector('dialog[open]')`);
 assert.equal(await evaluate(`document.querySelector('.literary-crush-content h3').textContent`),'Rhysand');
 await evaluate(`document.querySelector('.reader-literary-crush').scrollIntoView({block:'center'})`);
 const crushClip=await evaluate(`(()=>{const r=document.querySelector('.reader-literary-crush').getBoundingClientRect();return {x:r.left+scrollX,y:r.top+scrollY,width:r.width,height:r.height,scale:1}})()`);
 const crushShot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:crushClip});
 await (await import('node:fs/promises')).writeFile(new URL('../../../artifacts/profile-crush-card.png',import.meta.url),Buffer.from(crushShot.data,'base64'));
 await evaluate(`(()=>{const original=window.fetch;window.fetch=(url,opts)=>String(url).includes('/books?')?Promise.resolve(new Response(JSON.stringify({items:[1,2,3,4,5].map(n=>({id:'book-'+n,volumeInfo:{title:'Libro '+n,authors:['Autora']}}))}),{headers:{'Content-Type':'application/json'}})):original(url,opts)})()`);
 await click('[aria-label="Editar Mis libros imprescindibles"]');
 await until(`Boolean(document.querySelector('dialog input[type="search"]'))`);
 await fill('dialog input[type="search"]','Libro');
 await until(`document.querySelectorAll('.literary-highlight-results button').length===5`);
 for(let i=0;i<4;i++) {await click(`.literary-highlight-results li:nth-child(${i+1}) button`)}
 assert.equal(await evaluate(`document.querySelectorAll('.literary-highlight-selected li').length`),4);
 assert.equal(await evaluate(`document.querySelector('.literary-highlight-results li:last-child button').disabled`),true);
 await click('dialog button[type="submit"]');
 await until(`!document.querySelector('dialog[open]')`);
 assert.equal(await evaluate(`document.querySelectorAll('.literary-essential-shelf a').length`),4);
 await click('[aria-label="Editar Mis libros imprescindibles"]');
 await until(`document.querySelectorAll('.literary-highlight-selected li').length===4`);
 await click('.literary-highlight-selected li button');
 await evaluate(`window.profileModalTest.failSave=true`);
 await click('dialog button[type="submit"]');
 await until(`Boolean(document.querySelector('dialog [role="alert"]'))`);
 assert.equal(await evaluate(`document.querySelectorAll('.literary-essential-shelf a').length`),4);
 await evaluate(`window.profileModalTest.failSave=false`);
 await click('dialog button[type="submit"]');
 await until(`!document.querySelector('dialog[open]')`);
 assert.equal(await evaluate(`document.querySelectorAll('.literary-essential-shelf a').length`),3);
 for(const width of [1440,1024,390]) {
  await send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
  assert.ok(await evaluate(`document.documentElement.scrollWidth<=innerWidth+1`));
  assert.ok(await evaluate(`document.querySelector('.reader-literary-crush').getBoundingClientRect().top>=document.querySelector('.reader-story').getBoundingClientRect().bottom`));
 }
 console.log('PASS: edit/save crush; catalog selection; four-book limit; reopen/remove; failed-save preservation; desktop/tablet/mobile placement');
}finally{socket.close();await fetch(`${cdp}/json/close/${target.id}`)}
