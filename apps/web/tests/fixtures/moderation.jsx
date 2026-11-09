// Isolated API fixtures for browser tests. Never imported by the production app.
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes, Link } from 'react-router-dom'
import { AuthProvider, useAuth } from '/src/context/AuthContext'
import { ThemeProvider } from '/src/context/ThemeContext'
import { LibraryProvider } from '/src/context/LibraryContext'
import { authService } from '/src/services/authService'
import AdminGate from '/src/components/AdminGate'
import Layout from '/src/components/Layout'
import AdminEnvironmentPage from '/src/pages/AdminEnvironmentPage'
import SettingsPage from '/src/pages/SettingsPage'
import NotificationsPage from '/src/pages/NotificationsPage'
import ContentReportButton from '/src/components/ContentReportButton'
import ActivityOptionsMenu from '/src/components/ActivityOptionsMenu'
import CommentEntry from '/src/components/CommentEntry'
import BookReviews from '/src/components/BookReviews'
import '/src/styles.css'
import '/src/theme/themes.css'

const reader = new URLSearchParams(location.search).get('role') === 'reader'
localStorage.setItem('libria_token','isolated-moderation-browser-test')
authService.me = async () => ({id:'fixture',display_name:'Cuenta de prueba',role:reader?'lector':'admin',capabilities:[]})
const stamp='2026-11-09T12:00:00Z'
const original={id:'post',title:'Encuentro literario',body:'Versión pública conservada.',moderation_version:1,moderation_status:'approved',moderation_hidden:false,images:[]}
let pending=[['publication','rev-post'],['review','rev-review'],['comment','rev-comment']].map(([kind,id])=>({id,kind,content_id:'post',author:'Autora de prueba',title:'Encuentro literario',excerpt:'Propuesta para revisar',status:'pending_review',lifecycle:'active',base_version:1,created_at:stamp,findings:[{category:'amenazas',reason:'Requiere revisar el contexto de una cita.'}],proposal:{title:'Propuesta pendiente',body:'Texto completo propuesto.\nSegundo párrafo.'},current_content:{...original},public_version:{...original},attachments:[]}))
const all=pending.map(row=>({...row}))
let reports=[{id:'report-1',kind:'publication',content_id:'post',author:'Autora de prueba',reason:'spam',detail:'Contexto del reporte',status:'pending',created_at:stamp,report_count:1,excerpt:original.body,current_content:original,reported_content:{...original}}]
let auditHistory=[],notifications=[{id:'notice-1',revision_id:'rev-post',kind:'pending_review',message:'Tu contenido fue enviado a revisión. Te avisaremos cuando esté aprobado',created_at:stamp,read_at:null}]
window.moderationTest={requests:[],fail:null}
const realFetch=window.fetch.bind(window)
window.fetch=async(url,options={})=>{
  if(!String(url).includes('/api/'))return realFetch(url,options)
  const parsed=new URL(url),path=parsed.pathname.slice(4),method=options.method||'GET'
  window.moderationTest.requests.push({path,method,body:options.body})
  const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}})
  if(path==='/roles/access')return json({admin:!reader})
  if(path==='/accounts/me')return json({display_name:'Test account',username:'fixture',role:reader?'lector':'admin',email:'fixture@example.invalid',email_verified:true})
  if(path.startsWith('/admin/')&&reader)return json({detail:'Se requiere permiso administrativo'},403)
  if(path.startsWith('/admin/environment/'))return json({revision:'fixture',fields:[]})
  if(path==='/admin/moderation')return json({items:pending,total:pending.length,pending_reports:reports.filter(r=>r.status==='pending').length})
  if(path==='/admin/moderation/history')return json({items:auditHistory,total:auditHistory.length})
  if(path==='/admin/moderation/reports'){const items=reports.filter(r=>r.status===(parsed.searchParams.get('status')||'pending'));return json({items,total:items.length})}
  if(path.startsWith('/admin/moderation/reports/')){
    const id=path.split('/')[4],row=reports.find(r=>r.id===id)
    if(method==='POST'){
      const body=JSON.parse(options.body);row.status=body.action==='restored'?'hidden':body.action;row.current_content={...row.current_content,moderation_hidden:body.action==='hidden',moderation_version:row.current_content.moderation_version+1}
      auditHistory.unshift({id:crypto.randomUUID(),report_id:id,action:body.action,reason:body.reason,administrator:'Administradora',created_at:stamp,context:{previous:original,result:row.current_content}})
    }
    return json(row)
  }
  if(path.startsWith('/admin/moderation/')){
    const id=path.split('/')[3],row=all.find(r=>r.id===id)
    if(method==='POST'){
      if(window.moderationTest.fail){const status=window.moderationTest.fail;window.moderationTest.fail=null;return json({detail:'Conflicto de prueba'},status)}
      const body=JSON.parse(options.body);row.status=body.action;row.decision_reason=body.reason;pending=pending.filter(r=>r.id!==id)
      auditHistory.unshift({id:crypto.randomUUID(),revision_id:id,action:body.action,reason:body.reason,administrator:'Administradora',created_at:stamp,context:{previous:original,result:row.proposal}})
      notifications.unshift({id:crypto.randomUUID(),revision_id:id,kind:body.action,message:body.action==='approved'?'Tu publicación fue aprobada y ya está disponible en LibrIAverse':'Tu contenido no fue aprobado porque incumple nuestras normas de convivencia',decision_reason:body.reason,created_at:stamp,read_at:null})
    }
    return json(row)
  }
  if(path==='/me/moderation')return json({items:all,has_more:false})
  if(path.startsWith('/me/moderation/'))return json(all.find(r=>r.id===path.split('/').at(-1)))
  if(path==='/me/notifications')return json({items:notifications,has_more:false,unread_count:notifications.filter(n=>!n.read_at).length})
  if(path.startsWith('/me/notifications/')){const row=notifications.find(n=>n.id===path.split('/')[3]);row.read_at=stamp;return json(row)}
  if(path.startsWith('/content-reports/'))return json({id:'reported-once',status:'pending'},201)
  if(path.startsWith('/reviews/by-book/'))return json({items:[{id:'book-review',author:'Lectora',body:'Una reseña publicada',published_at:stamp,dimension_ratings:{}}],has_more:false})
  return json([])
}
export function Community(){return <section><h1>Comunidad de prueba</h1><ActivityOptionsMenu item={{id:'post',feed_item_type:'publication'}}/><ContentReportButton kind="publication" identifier="event"/><CommentEntry comment={{id:'comment',author:'Lectora',body:'Comentario publicado',created_at:stamp}} userId="fixture"/><BookReviews bookRef="work"/></section>}
export default function Fixture(){const{user,loading}=useAuth();return user&&!loading?<Routes><Route element={<Layout/>}><Route element={<AdminGate/>}><Route path="/admin/environment" element={<AdminEnvironmentPage/>}/></Route><Route path="/settings" element={<SettingsPage/>}/><Route path="/notifications" element={<NotificationsPage/>}/><Route path="/profile" element={<h1>Mi actividad</h1>}/><Route path="*" element={<><Link to="/admin/environment#content-moderation">Configuración</Link><Community/></>}/></Route></Routes>:null}
history.replaceState({},'',reader?'/community':'/admin/environment#content-moderation')
createRoot(document.getElementById('root')).render(<BrowserRouter><AuthProvider><ThemeProvider><LibraryProvider><Fixture/></LibraryProvider></ThemeProvider></AuthProvider></BrowserRouter>)
