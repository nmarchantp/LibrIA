import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function LoginPage(){const{login}=useAuth();const navigate=useNavigate();const[error,setError]=useState('');const submit=async(e)=>{e.preventDefault();setError('');const form=new FormData(e.currentTarget);try{await login({email:form.get('email'),password:form.get('password')});navigate('/')}catch{setError('No fue posible iniciar sesión. Revisa tus datos y que la API esté activa.')}};return <main className="auth-page"><form className="auth-card" onSubmit={submit}><h1>Bienvenida a LibrIA</h1><label>Correo<input name="email" type="email" required/></label><label>Contraseña<input name="password" type="password" required/></label>{error&&<p className="form-error" role="alert">{error}</p>}<button className="button primary">Ingresar</button><p>¿Aún no tienes cuenta? <Link to="/register">Regístrate</Link></p></form></main>}
