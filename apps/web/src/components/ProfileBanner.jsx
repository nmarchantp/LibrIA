import { useEffect, useLayoutEffect, useRef, useState } from 'react'
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

export default function ProfileBanner({ panoramic = false }) {
  const coverRef = useRef(null)
  const { theme } = useTheme()
  // This is the last decoded image, not a second theme preference.
  const [visibleBanner, setVisibleBanner] = useState(defaultProfileBanner)
  useEffect(() => {
    let active = true
    const requested = getProfileBanner(theme,panoramic)
    async function load() {
      let next = requested
      try { await preload(requested.src) }
      catch {
        next = panoramic ? getProfileBanner(theme) : defaultProfileBanner
        try { await preload(next.src) } catch { return }
      }
      // A slower response from a previous theme must never replace the latest one.
      if (active) setVisibleBanner(next)
    }
    load()
    return () => { active = false }
  }, [theme,panoramic])

  useLayoutEffect(() => {
    if (!panoramic || !coverRef.current) return
    const cover = coverRef.current
    const top = cover.closest('.reader-profile-top')
    const feather = top?.querySelector('.reader-profile-name-feather')
    const name = top?.querySelector('.reader-profile-name')
    const message = document.querySelector('.social-topbar a[href="/messages"]')
    const update = () => {
      const bounds = cover.getBoundingClientRect()
      if (!bounds.width) return
      const scale = cover.clientWidth / bounds.width
      const marker = feather?.getBoundingClientRect() || name?.getBoundingClientRect()
      const left = Math.max(0, Math.min(cover.clientWidth, marker ? (marker.right - bounds.left) * scale : cover.clientWidth * .3))
      const right = Math.max(left, Math.min(cover.clientWidth, message ? (message.getBoundingClientRect().left - bounds.left) * scale : cover.clientWidth * .88))
      cover.style.setProperty('--profile-fade-left', `${left}px`)
      cover.style.setProperty('--profile-fade-right', `${right}px`)
      cover.style.setProperty('--profile-cover-width', `${cover.clientWidth}px`)
    }
    const observer = new ResizeObserver(update)
    for (const element of [cover, top, feather, message, name]) if (element) observer.observe(element)
    window.addEventListener('resize', update)
    update()
    return () => { observer.disconnect(); window.removeEventListener('resize', update) }
  }, [panoramic])

  return <div ref={coverRef} className={`reader-profile-cover${panoramic ? ' reader-profile-cover--panoramic' : ''}`} aria-hidden="true" style={{ '--banner-position': visibleBanner.position, '--banner-mobile-position': visibleBanner.mobilePosition }}>
    <img src={visibleBanner.src} alt="" decoding="async" fetchPriority="high" />
  </div>
}
