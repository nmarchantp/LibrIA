import { Link } from 'react-router-dom'
import { BadgeCheck } from 'lucide-react'

const labels = { lector: 'Lector', influencer: 'Influencer', autor: 'Autor', libreria: 'Librer?a', admin: 'Administrador' }

export default function RoleManagementPanel({ user }) {
  return <section className="role-panel" aria-labelledby="account-role-heading">
    <h2 id="account-role-heading"><BadgeCheck size={22} aria-hidden="true" />Tipo de perfil</h2>
    <p>Perfil asignado: <strong>{labels[user.role]}</strong></p>
    <p>Solo un administrador autorizado puede solicitar y aprobar cambios de tipo de perfil.</p>
    {user.role === 'admin' && <Link className="button primary" to="/admin/profiles">Administrar cuentas</Link>}
  </section>
}
