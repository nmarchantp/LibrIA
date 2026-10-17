import { useAuth } from '../context/AuthContext'
import GoogleAccountPanel from '../components/GoogleAccountPanel'
import RoleManagementPanel from '../components/RoleManagementPanel'

const roles = { lector: 'Lector', autor: 'Autor', influencer: 'Influencer', libreria: 'Librería', admin: 'Administrador' }

export default function AccountPage() {
  const { user } = useAuth()
  return <div className="account-page">
    <section className="google-account-panel"><h2>Mi cuenta</h2>
      <dl className="account-details">
        <div><dt>Nombre</dt><dd>{user.display_name}</dd></div>
        <div><dt>Correo de LibrIA</dt><dd>{user.email}</dd></div>
        <div><dt>Tipo de cuenta</dt><dd>{roles[user.role] || user.role}</dd></div>
        <div><dt>Biografía</dt><dd>{user.biography || 'Sin biografía'}</dd></div>
        <div><dt>Miembro desde</dt><dd>{new Date(user.created_at).toLocaleDateString('es-CL')}</dd></div>
      </dl>
      <p>Ingreso con correo y contraseña habilitado.</p>
    </section>
    <GoogleAccountPanel />
    <RoleManagementPanel user={user} />
  </div>
}
