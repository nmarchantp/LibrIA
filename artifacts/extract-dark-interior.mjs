import { readFileSync, writeFileSync } from 'node:fs'
const file='apps/web/src/pages/MuralIdentity.css'
let css=readFileSync(file,'utf8')
const start=css.indexOf(':root[data-theme="dark"]')
const end=css.indexOf('\n}',start)+2
const tokens=css.slice(css.indexOf('{',start)+1,end-1)
css=css.slice(0,start)+css.slice(end)
const marker=css.indexOf('/* Only the dark mural')
const open=css.indexOf('{',marker)
let depth=1,cursor=open+1,shared='',local=''
const localSelector=s=>/mural-heading|mural-audiences|reader-summary|aside-reading|feed-card|mural-category|community-note/.test(s)
while(depth&&cursor<css.length){
 const begin=cursor
 while(/\s/.test(css[cursor]))cursor++
 if(css[cursor]==='}')break
 const brace=css.indexOf('{',cursor)
 const selector=css.slice(cursor,brace).trim()
 let count=1;cursor=brace+1
 while(count&&cursor<css.length){if(css[cursor]==='{')count++;if(css[cursor]==='}')count--;cursor++}
 const rule=css.slice(begin,cursor)
 // The initial background declaration belongs to the shared shell.
 if(selector.includes('background:var(--paper);')){
  shared+='\n  background:var(--paper);'
  shared+=rule.replace('background:var(--paper);','')
 }else if(localSelector(selector))local+=rule
 else shared+=rule
}
css=css.slice(0,open+1)+local+'\n'+css.slice(cursor)
const scope=':root[data-theme="dark"] .social-shell[data-interior-style="literary"]'
const output=`/* Shared dark interior, extracted from the approved mural. */\n:root[data-theme="dark"] :is(.social-shell[data-interior-style="literary"],.reader-profile-modal[open],.content-management-dialog[open]) {${tokens}\n}\n${scope} {${shared}\n  .literary-atmosphere { display:none; }\n  .social-sidebar > .brand-link { position:relative; isolation:isolate; border-bottom:1px solid #594064; }\n  .social-sidebar > .brand-link::after { content:''; position:absolute; width:72px; height:24px; right:10px; top:3px; border-top:1px solid var(--accent); border-radius:50%; transform:rotate(-15deg); opacity:.55; pointer-events:none; }\n}\n@media(max-width:700px) {\n  ${scope} {\n    .social-page-column { --main-top-space:14px; }\n    .sidebar-navigation::after { display:none; }\n    .social-sidebar > .brand-link { padding:0; border:0; }\n    .social-sidebar > .brand-link::before,.social-sidebar > .brand-link::after { display:none; }\n    .profile-starfield::before { height:150px; background-position:68% top; opacity:.8; }\n    .sidebar-navigation { background:radial-gradient(ellipse at 50% 100%,rgb(96 51 122 / 18%),transparent 65%),#211B2E; }\n    .social-nav a.active { box-shadow:inset 0 2px #C4A2F0; }\n  }\n}\n`
writeFileSync('apps/web/src/components/DarkInterior.css',output)
writeFileSync(file,css)
