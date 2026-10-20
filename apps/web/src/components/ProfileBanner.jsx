import { useEffect, useState } from 'react'
import { useTheme } from '../context/ThemeContext'
import { defaultProfileBanner, getProfileBanner } from '../theme/profileBanners'

// Reuse decoded images on tab/theme changes. Load only the requested landscape.
const decodedImages = new Map()
function preload(src) {
  if (!decodedImages.has(src)) {
    const pending = new Promise((resolve, reject) => {
      const image = new Image()
      image.decoding = 'async'
      image.onload = () => image.decode().then(() => resolve(image), reject)
      image.onerror = () => reject(new Error('Banner unavailable'))
      image.src = src
    }).catch(error => {
      decodedImages.delete(src)
      throw error
    })
    decodedImages.set(src, pending)
  }
  return decodedImages.get(src)
}

export default function ProfileBanner() {
  const { theme } = useTheme()
  // This is the last decoded image, not a second theme preference.
  const [visibleBanner, setVisibleBanner] = useState(defaultProfileBanner)
  useEffect(() => {
    let active = true
    const requested = getProfileBanner(theme)
    async function load() {
      let next = requested
      try { await preload(requested.src) }
      catch {
        next = defaultProfileBanner
        try { await preload(next.src) } catch { return }
      }
      // A slower response from a previous theme must never replace the latest one.
      if (active) setVisibleBanner(next)
    }
    load()
    return () => { active = false }
  }, [theme])

  return <div className="reader-profile-cover" aria-hidden="true" style={{ '--banner-position': visibleBanner.position, '--banner-mobile-position': visibleBanner.mobilePosition }}>
    <img src={visibleBanner.src} alt="" decoding="async" fetchPriority="high" />
  </div>
}
