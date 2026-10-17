import { apiUrl } from '../api/client'

export default function GoogleLoginButton() {
  return <a className="button google-login" href={apiUrl('/auth/google/login')}>
    Continuar con Google
  </a>
}
