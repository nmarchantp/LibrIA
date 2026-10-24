import { useAuth } from '../context/AuthContext'
import GoogleAccountPanel from '../components/GoogleAccountPanel'
import RoleManagementPanel from '../components/RoleManagementPanel'
import './AccountPage.css'

const roles = { lector: 'Lector', autor: 'Autor', influencer: 'Influencer', libreria: 'Librería', admin: 'Administrador' }

export default function AccountPage({ biography }) {
  const { user } = useAuth()
  return <div className="account-page">
    <section className="account-personal-info" aria-labelledby="account-personal-heading"><h2 id="account-personal-heading"><UserRound size={22} aria-hidden="true" />Información personal</h2>
      <dl className="account-details">
        <div><dt>Nombre</dt><dd>{user.display_name}</dd></div>
        <div><dt>Correo electrónico</dt><dd>{user.email}</dd></div>
        <div><dt>Tipo de cuenta</dt><dd>{roles[user.role] || user.role}</dd></div>
        <div><dt>Miembro desde</dt><dd>{new Date(user.created_at).toLocaleDateString('es-CL')}</dd></div>
      </dl>
      <dl className="account-biography"><div><dt>Biografía</dt><dd>{(biography === undefined ? user.biography : biography) || 'Sin biografía'}</dd></div></dl>
      <p className="account-sign-in-note">Ingreso con correo y contraseña habilitado.</p>
    </section>
    <GoogleAccountPanel />
    <RoleManagementPanel user={user} />
  </div>
}
import { UserRound } from 'lucide-react'
