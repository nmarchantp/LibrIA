import {writeFile,mkdir} from 'node:fs/promises';
const target=await (await fetch('http://127.0.0.1:9224/json/new?about:blank',{method:'PUT'})).json();
const ws=new WebSocket(target.webSocketDebuggerUrl); await new Promise(r=>ws.onopen=r);
let id=0;const pending=new Map(); ws.onmessage=e=>{const m=JSON.parse(e.data); if(m.id){pending.get(m.id)?.(m);pending.delete(m.id)}};
const send=(method,params={})=>new Promise(r=>{pending.set(++id,r);ws.send(JSON.stringify({id,method,params}))});
const ev=async expression=>{const m=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(m.result?.exceptionDetails)throw Error(JSON.stringify(m.result.exceptionDetails));return m.result.result.value};
const pause=ms=>new Promise(r=>setTimeout(r,ms));
try{
await send('Emulation.setFocusEmulationEnabled',{enabled:true});await send('Page.bringToFront');await send('Emulation.setDeviceMetricsOverride',{width:1100,height:1000,deviceScaleFactor:1,mobile:false});
await send('Page.navigate',{url:'http://localhost:5173/tests/fixtures/profile-modals.html?role=admin'});
for(let i=0;i<100;i++){if(await ev('!!document.querySelector(".social-main")'))break;await pause(100)}
await ev(`history.pushState({},'','/');window.dispatchEvent(new PopStateEvent('popstate'))`);await pause(1000);
await ev(`(async()=>{const {default:React}=await import('/node_modules/.vite/deps/react.js');const {default:{createRoot}}=await import('/node_modules/.vite/deps/react-dom_client.js');const {AuthProvider}=await import('/src/context/AuthContext.jsx');const {default:PostComposer}=await import('/src/components/PostComposer.jsx');document.getElementById('root').style.display='none';const host=document.createElement('main');host.id='focus-fixture';host.style.cssText='max-width:700px;margin:24px auto';document.body.append(host);createRoot(host).render(React.createElement(AuthProvider,null,React.createElement(PostComposer,{role:'admin',profileId:'fixture'})))})()`);await pause(500);
await mkdir('artifacts/focus',{recursive:true});
const themes=await ev(`import('/src/theme/themes.js').then(m=>m.themes.map(t=>t.id))`);
const results=[];
for(const theme of themes){
await ev(`import('/src/theme/themes.js').then(m=>m.applyTheme(${JSON.stringify(theme)}))`);
await ev(`document.querySelector('#focus-fixture .composer-editor textarea').focus()`);await pause(220);
const metrics=await ev(`(()=>{let e=document.querySelector('#focus-fixture .composer-editor textarea'),p=e.closest('.composer-editor'),s=getComputedStyle(e),c=getComputedStyle(p);let r=p.getBoundingClientRect();return {theme:document.documentElement.dataset.theme,childOutline:s.outlineStyle,childShadow:s.boxShadow,outline:c.outlineWidth,outlineColor:c.outlineColor,border:c.borderColor,shadow:c.boxShadow,width:r.width,height:r.height}})()`);
if(metrics.childOutline!=='none'||metrics.childShadow!=='none'||metrics.outline!=='2px'||metrics.shadow!=='none')throw Error(JSON.stringify(metrics));
await ev(`document.querySelector('#focus-fixture .composer-editor textarea').blur()`);await pause(200);
const size=await ev(`(()=>{const r=document.querySelector('#focus-fixture .composer-editor').getBoundingClientRect();return [r.width,r.height]})()`);if(size[0]!==metrics.width||size[1]!==metrics.height)throw Error('layout shift');
// Actual Tab input dispatch: title -> textarea, preserving normal tab order.
await ev(`document.querySelector('#focus-fixture .composer-title').focus()`);
await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});await pause(220);
metrics.tab=await ev(`document.activeElement.matches('.composer-editor textarea:focus-visible')`);if(!metrics.tab)throw Error('Tab did not reach textarea');
await ev(`document.querySelector('#focus-fixture .composer').scrollIntoView({block:'start'})`);
const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile('artifacts/focus/'+theme+'.png',Buffer.from(shot.result.data,'base64'));
const fields=await ev(`(()=>{const host=document.createElement('div');host.innerHTML='<div class="settings-page"><div class="account-page"><form><input type="email"><input type="password"><input type="search"><textarea></textarea><select><option>Opcion</option></select><input disabled><input aria-invalid="true" style="border:1px solid var(--error-text)"></form></div></div>';document.body.append(host);const fields=[...host.querySelectorAll('input,textarea,select')];const results=fields.map(e=>{const before=e.getBoundingClientRect();const border=getComputedStyle(e).borderColor;e.focus();const c=getComputedStyle(e),after=e.getBoundingClientRect();return {type:e.type,disabled:e.disabled,invalid:e.getAttribute('aria-invalid'),outline:c.outlineWidth,shadow:c.boxShadow,sameSize:before.width===after.width&&before.height===after.height,errorPreserved:e.getAttribute('aria-invalid')!=='true'||border===c.borderColor}});host.remove();return results})()`);
for(const field of fields){if(!field.sameSize||!field.errorPreserved||(!field.disabled&&(field.outline!=='2px'||field.shadow!=='none')))throw Error(JSON.stringify(field))}
metrics.fields=fields;results.push(metrics);
}
await writeFile('artifacts/focus/results.json',JSON.stringify(results,null,2));console.log('PASS nine themes: one indicator, no glow, no layout shift, keyboard Tab; screenshots saved');
}finally{ws.close();await fetch('http://127.0.0.1:9224/json/close/'+target.id)}






