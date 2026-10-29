import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function AdminGate() {
  const { access, accessLoading } = useAuth()
  if (accessLoading) return <p role="status">Comprobando permisos…</p>
  return access?.admin ? <Outlet /> : <Navigate to="/" replace />
}
