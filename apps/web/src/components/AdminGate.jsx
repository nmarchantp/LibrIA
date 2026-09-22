import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function AdminGate() {
  const { user } = useAuth()
  return user?.role === 'admin' ? <Outlet /> : <Navigate to="/" replace />
}
