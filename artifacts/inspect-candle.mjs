const tabs=await(await fetch('http://127.0.0.1:9224/json/list')).json()
for(const tab of tabs.filter(t=>t.type==='page'&&/127\.0\.0\.1|localhost|192\.168\./.test(t.url))){
 const ws=new WebSocket(tab.webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r)
 const result=await new Promise(resolve=>{ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id===1)resolve(m.result?.result?.value)};ws.send(JSON.stringify({id:1,method:'Runtime.evaluate',params:{expression:`JSON.stringify({path:location.pathname,theme:document.documentElement.dataset.theme,reduced:matchMedia('(prefers-reduced-motion:reduce)').matches,background:localStorage.getItem('libriaverse-magical-background'),motion:localStorage.getItem('libriaverse-magical-background-motion'),flame:!!document.querySelector('.sidebar-candle-flame-shape'),animation:document.querySelector('.sidebar-candle-flame-shape')?getComputedStyle(document.querySelector('.sidebar-candle-flame-shape')).animationName:null})`,returnByValue:true}}))})
 console.log(result);ws.close()
}
