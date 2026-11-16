import { themes } from './themes'

const originals = { flowers: '/images/story-books-candles.png', books: '/images/story-books-coffee.png', cat: '/images/story-books-cat-candle-left.png' }

export function getStoryArtwork(themeId) {
  const theme = themes.find(item => item.id === themeId)
  if (themeId === 'dark-blood') return { images: Object.fromEntries(Object.keys(originals).map(key => [key, `/images/profile-story-v2/blood-${key}.png`])), filter: 'none' }
  const color = theme?.colors[2] || '#7856A4'
  const [r, g, b] = color.match(/[a-f\d]{2}/gi).map(value => parseInt(value, 16) / 255)
  const max = Math.max(r, g, b), min = Math.min(r, g, b), delta = max - min
  const hue = !delta ? 280 : ((max === r ? (g - b) / delta : max === g ? (b - r) / delta + 2 : (r - g) / delta + 4) * 60 + 360) % 360
  return { images: originals, filter: `hue-rotate(${Math.round(hue - 280)}deg) saturate(.8) brightness(${theme?.group === 'dark' ? '.85' : '1'})` }
}
