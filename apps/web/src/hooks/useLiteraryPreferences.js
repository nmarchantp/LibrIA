import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { profileService } from '../services/profileService'

export default function useLiteraryPreferences(profileId) {
  const { user } = useAuth()
  const identity = `${user.id}:${profileId || 'me'}`
  const currentIdentity = useRef(identity)
  currentIdentity.current = identity
  const [result, setResult] = useState({ identity, data: null, loading: true, error: '' })
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    setResult({ identity, data: null, loading: true, error: '' })
    const request = profileId ? profileService.community(profileId) : profileService.mine()
    request.then(data => { if (active) setResult({ identity, data, loading: false, error: '' }) })
      .catch(cause => { if (active) setResult({ identity, data: null, loading: false, error: cause.status === 404 ? 'Perfil no encontrado.' : 'No se pudo cargar el perfil. Intenta nuevamente.' }) })
    return () => { active = false }
  }, [identity, profileId, attempt])
  const save = useCallback(async fields => {
    if (profileId) throw new Error('La vista comunitaria es de solo lectura.')
    const data = await profileService.save(fields)
    if (currentIdentity.current !== identity) throw new Error('La sesión cambió. Recarga el perfil.')
    setResult({ identity, data, loading: false, error: '' })
    return data
  }, [identity, profileId])
  const visible = result.identity === identity ? result : { data: null, loading: true, error: '' }
  return { ...visible, save, retry: () => setAttempt(value => value + 1) }
}
