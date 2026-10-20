// Visual assets only. Keep the existing persisted theme IDs unchanged.
export const defaultProfileBanner = {
  src: '/images/profile-reading-nook.png',
  position: 'center 52%',
  mobilePosition: 'center 52%',
}

export const profileBanners = {
  lavanda: { src: '/images/profile-banners/lavender.webp', position: 'center 35%', mobilePosition: 'center 52%' },
  otono: { src: '/images/profile-banners/autumn.webp', position: 'center 35%', mobilePosition: 'center 52%' },
  invierno: { src: '/images/profile-banners/winter.webp', position: 'center 35%', mobilePosition: 'center 52%' },
  dark: { src: '/images/profile-banners/dark.webp', position: 'center 35%', mobilePosition: 'center 52%' },
  bosque: { src: '/images/profile-banners/forest.webp', position: 'center 35%', mobilePosition: 'center 52%' },
  'rosa-antiguo': { src: '/images/profile-banners/rose.webp', position: 'center 35%', mobilePosition: 'center 52%' },
}

export function getProfileBanner(theme) {
  return profileBanners[theme] || defaultProfileBanner
}
