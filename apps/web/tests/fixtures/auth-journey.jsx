import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useAuthJourney } from '../../src/context/AuthJourneyContext'
import { AuthProvider, useAuth } from '../../src/context/AuthContext'
import AuthJourneyProvider from '../../src/components/AuthJourneyProvider'
import SessionGate from '../../src/components/SessionGate'
import LoginPage from '../../src/pages/LoginPage'
import RegisterPage from '../../src/pages/RegisterPage'
import { ThemeProvider } from '../../src/context/ThemeContext'
import { LibraryProvider } from '../../src/context/LibraryContext'
import registrationGenres from './registration-genres.json'
import registrationTropes from './registration-tropes.json'
import { registrationBooks } from './registration-books'
import '../../src/styles.css'
import { applyTheme } from '../../src/theme/themes'
applyTheme('lavanda')
const user={id:'test-reader',display_name:'Lector',email:'reader@example.com',role:'lector',onboarding_required:false}
const session={session_id:'journey-test',inactivity_expires_at:'2099-01-01T00:00:00Z',absolute_expires_at:'2099-01-01T00:00:00Z'}
window.journeyTest={calls:[],success:false}
let progress={status:'pending',step:1,answers:{},emotions:['Ternura','Intriga','Adrenalina','Asombro','Nostalgia','Inspiración','Alegría','Esperanza','Melancolía','Suspenso','Miedo','Sorpresa','Pasión','Empatía','Serenidad','Diversión','Conmoción','Euforia'],habits:['Leo ocasionalmente'],ai_status:'pending',recommendations:[]}
window.fetch=async(input,options={})=>{
 const path=new URL(input,location.href).pathname
 const body=typeof options.body==='string'?JSON.parse(options.body):null
 window.journeyTest.calls.push({path,body})
 const response=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}})
 if(path.endsWith('/auth/logout'))return response({},window.journeyTest.failLogout?500:200)
 if(path.endsWith('/auth/refresh'))return response({},401)
 if(path.endsWith('/profiles/me/onboarding')){
  if(options.method==='PATCH'){
   if(body.complete){
    await new Promise(resolve=>setTimeout(resolve,400))
    progress={...progress,guide:{version:1,step:'analysis'},ai_status:window.journeyTest.pendingRecommendations?'processing':'completed',ai_available:true,recommendation_source:'gemini',generated_at:'2026-11-17T12:00:00Z',
      dna:{profile_name:'Explorador de universos',profile_description:'Te atraen la fantasía y los misterios.',preferred_genres:['Fantasía'],explanation:'Basado en tus preferencias declaradas.'},
      recommendations:registrationBooks.filter(book=>!body.answers.favorite_work_ids.includes(book.id)).map(book=>({work_id:book.id,title:book.volumeInfo.title,authors:book.volumeInfo.authors,cover_url:book.volumeInfo.imageLinks.thumbnail,explanation:'Conecta con tus preferencias declaradas.'}))}
   }
   if(body.complete && window.journeyTest.pendingRecommendations) progress.recommendations.push(...progress.recommendations.map(book=>({...book,work_id:book.work_id+'-extra'})))
   progress={...progress,...body,status:body.complete?'completed':'in_progress'}
   if(body.complete)user.onboarding_required=false
  }
  return response(progress)
 }
 if(path.endsWith('/profiles/preference-catalogs'))return response({genres:registrationGenres,tropes:registrationTropes})
 if(path.endsWith('/books'))return response({items:window.journeyTest.longBookTitles?registrationBooks.map(book=>({...book,volumeInfo:{...book.volumeInfo,title:book.volumeInfo.title+' (Edicion especial de coleccion con un titulo extraordinariamente largo para verificar los margenes)',authors:Array(8).fill(book.volumeInfo.authors[0])}})):registrationBooks,has_more:false})
 if(path.endsWith('/readings/me'))return response([])
 if(path.endsWith('/readings/library')&&options.method==='POST')return response({id:'carousel-reading',work_id:body.work_id,book_ref:body.work_id,status:'pending'})
 if(path.endsWith('/auth/login')||path.endsWith('/auth/register'))return window.journeyTest.success?response({...session,user,access_token:'journey-token'}):response({detail:'Invalid credentials'},401)
 if(path.endsWith('/auth/me'))return response(user)
 if(path.endsWith('/auth/session')||path.endsWith('/auth/activity'))return response(session)
 if(path.endsWith('/roles/access'))return response({})
 return response({})
}
localStorage.removeItem('libria_token');localStorage.removeItem('libria_session')
export default function Destination(){const {logout}=useAuth();const {run,holding}=useAuthJourney();const navigate=useNavigate();return <><h1>Destino de prueba</h1><button className="journey-logout" disabled={holding} onClick={()=>run('exit',logout,()=>navigate('/login',{replace:true}))}>Cerrar sesión</button></>}
createRoot(document.getElementById('root')).render(<BrowserRouter><ThemeProvider><AuthProvider><LibraryProvider><AuthJourneyProvider><Routes><Route element={<SessionGate guest />}><Route path="/login" element={<LoginPage />} /><Route path="/register" element={<RegisterPage />} /></Route><Route element={<SessionGate />}><Route path="/profiles/:id" element={<Destination />} /><Route path="/profile" element={<Destination />} /></Route><Route path="*" element={<Navigate to="/login?next=%2Fprofiles%2Freader-one" replace />} /></Routes></AuthJourneyProvider></LibraryProvider></AuthProvider></ThemeProvider></BrowserRouter>)
