import { Link } from 'react-router-dom'
import './ProfilePreferences.css'
import ProfileFavoriteQuotes from './ProfileFavoriteQuotes'
import ProfileReadingChallenge from './ProfileReadingChallenge'

export default function ProfilePersonalColumn({ editMode = false, preferencesState }) {
  const { data: preferences, loading, error, retry: onRetry, save: onSave } = preferencesState
  return <aside className="reader-personal-column" aria-label="Tu espacio personal">
    <ProfileReadingChallenge />
    <ProfileFavoriteQuotes editable={editMode} quotes={preferences?.favorite_quotes} loading={loading} error={error} onRetry={onRetry} onSave={onSave} />
    {preferences?.profile_id && <Link className="reader-public-profile-link" to={`/profiles/${preferences.profile_id}`}>Ver mi perfil comunitario</Link>}
  </aside>
}
