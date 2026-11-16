import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useAuthJourney } from '../../src/context/AuthJourneyContext'
import { AuthProvider, useAuth } from '../../src/context/AuthContext'
import AuthJourneyProvider from '../../src/components/AuthJourneyProvider'
import SessionGate from '../../src/components/SessionGate'
import LoginPage from '../../src/pages/LoginPage'
import RegisterPage from '../../src/pages/RegisterPage'
import '../../src/styles.css'
import { applyTheme } from '../../src/theme/themes'
applyTheme('lavanda')
const user={id:'test-reader',display_name:'Lector',email:'reader@example.com',role:'lector'}
const session={session_id:'journey-test',inactivity_expires_at:'2099-01-01T00:00:00Z',absolute_expires_at:'2099-01-01T00:00:00Z'}
window.journeyTest={calls:[],success:false}
window.fetch=async(input,options={})=>{
 const path=new URL(input,location.href).pathname
 const body=typeof options.body==='string'?JSON.parse(options.body):null
 window.journeyTest.calls.push({path,body})
 const response=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}})
 if(path.endsWith('/auth/logout'))return response({},window.journeyTest.failLogout?500:200)
 if(path.endsWith('/auth/refresh'))return response({},401)
 if(path.endsWith('/auth/login')||path.endsWith('/auth/register'))return window.journeyTest.success?response({...session,user,access_token:'journey-token'}):response({detail:'Invalid credentials'},401)
 if(path.endsWith('/auth/me'))return response(user)
 if(path.endsWith('/auth/session')||path.endsWith('/auth/activity'))return response(session)
 if(path.endsWith('/roles/access'))return response({})
 return response({})
}
localStorage.removeItem('libria_token');localStorage.removeItem('libria_session')
export default function Destination(){const {logout}=useAuth();const {run,holding}=useAuthJourney();const navigate=useNavigate();return <><h1>Destino de prueba</h1><button className="journey-logout" disabled={holding} onClick={()=>run('exit',logout,()=>navigate('/login',{replace:true}))}>Cerrar sesión</button></>}
createRoot(document.getElementById('root')).render(<BrowserRouter><AuthProvider><AuthJourneyProvider><Routes><Route element={<SessionGate guest />}><Route path="/login" element={<LoginPage />} /><Route path="/register" element={<RegisterPage />} /></Route><Route element={<SessionGate />}><Route path="/profiles/:id" element={<Destination />} /></Route><Route path="*" element={<Navigate to="/login?next=%2Fprofiles%2Freader-one" replace />} /></Routes></AuthJourneyProvider></AuthProvider></BrowserRouter>)
