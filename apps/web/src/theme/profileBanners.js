import { literaryThemes } from './literaryThemes'

// Visual assets only. Keep the existing persisted theme IDs unchanged.
export const defaultProfileBanner = {
  src: '/images/profile-reading-nook.png',
  position: 'center 52%',
  mobilePosition: 'center 52%',
}

export const profileBanners = {
  ...Object.fromEntries(literaryThemes.filter(theme => theme.art).map(theme => [theme.id, { src:theme.art.banner, position:'center', mobilePosition:'70% center' }])),
  'dark-rosado': { src: '/images/rose-universe/moonlit-garden-v1.png', position: 'center', mobilePosition: '70% center' },
  lavanda: { src: '/images/theme-refresh-v1/lavanda/banner.webp', position: 'center', mobilePosition: '70% center' },
  otono: { src: '/images/theme-refresh-v1/otono/banner.webp', position: 'center', mobilePosition: '70% center' },
  invierno: { src: '/images/theme-refresh-v1/invierno/banner.webp', position: 'center', mobilePosition: '70% center' },
  dark: { src: '/images/theme-refresh-v1/dark/banner.webp', position: 'center', mobilePosition: '70% center' },
  'dark-blood': { src: '/images/blood-universe/gothic-study-v2.webp', position: 'right 68%', mobilePosition: '72% 68%' },
  'dark-dorado': { src: '/images/theme-refresh-v1/dark-dorado/banner.webp', position: 'center', mobilePosition: '70% center' },
  bosque: { src: '/images/theme-refresh-v1/bosque/banner.webp', position: 'center', mobilePosition: '70% center' },
  'rosa-antiguo': { src: '/images/theme-refresh-v1/rosa-antiguo/banner.webp', position: 'center', mobilePosition: '70% center' },
}

export function getProfileBanner(theme) {
  return profileBanners[theme] || defaultProfileBanner
}
