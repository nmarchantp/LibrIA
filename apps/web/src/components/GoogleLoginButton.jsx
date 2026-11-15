import { apiUrl } from '../api/client'
import { useLocation } from 'react-router-dom'
import { rememberProfileDestination } from '../services/profileDestination'

export default function GoogleLoginButton() {
  const location = useLocation()
  return <a className="button google-login" href={apiUrl('/auth/google/login')} onClick={() => rememberProfileDestination(location.search)}>
    <svg className="google-brand-icon" width="20" height="20" viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      <path fill="#4285F4" d="M43.6 24.5c0-1.5-.1-2.9-.4-4.3H24v8.2h11a9.4 9.4 0 0 1-4.1 6.2v5.2h6.7c3.9-3.6 6-8.8 6-15.3Z" />
      <path fill="#34A853" d="M24 44c5.5 0 10.1-1.8 13.5-4.9l-6.7-5.2a12.3 12.3 0 0 1-18.3-6.5H5.6v5.3A20.4 20.4 0 0 0 24 44Z" />
      <path fill="#FBBC05" d="M12.5 27.4a12.2 12.2 0 0 1 0-7.8v-5.3H5.6a20.4 20.4 0 0 0 0 18.4l6.9-5.3Z" />
      <path fill="#EA4335" d="M24 11.3c3 0 5.7 1 7.8 3l5.9-5.9A19.7 19.7 0 0 0 24 3a20.4 20.4 0 0 0-18.4 11.3l6.9 5.3A12.2 12.2 0 0 1 24 11.3Z" />
    </svg>
    Continuar con Google
  </a>
}
