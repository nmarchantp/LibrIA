import { apiUrl } from '../api/client'
import { useLocation } from 'react-router-dom'
import { rememberProfileDestination } from '../services/profileDestination'

export default function GoogleLoginButton() {
  const location = useLocation()
  return <a className="button google-login" href={apiUrl('/auth/google/login')} onClick={() => rememberProfileDestination(location.search)}>
    Continuar con Google
  </a>
}
