import { useEffect, useState } from 'react'
import { accountRequest } from '../services/onboardingService'

export default function PublicLiteraryDNA({ profileId, preview = false }) {
  const [value, setValue] = useState(null)
  useEffect(() => {
    const controller = new AbortController()
    setValue(null)
    accountRequest(`/profiles/${profileId}/literary-dna${preview ? '?preview=true' : ''}`, { signal: controller.signal }).then(result => {
      if (!controller.signal.aborted) setValue(result.dna)
    }).catch(() => {})
    return () => controller.abort()
  }, [profileId, preview])
  return value ? <section className="reader-personal-card"><h2>Mi ADN literario</h2><h3>{value.profile_name}</h3><p>{value.profile_description}</p><p>{value.preferred_genres.join(' · ')}</p><p>{value.explanation}</p><small>Basado en preferencias declaradas.</small></section> : null
}
