import { themes } from '../theme/themes'

// A white quiet zone and dark variants keep every palette readable by scanners.
function scanColor(hex) {
  let rgb = hex.match(/[a-f\d]{2}/gi).map(value => parseInt(value, 16))
  const luminance = channels => channels.map(value => {
    const channel = value / 255
    return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4
  }).reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0)
  while (luminance(rgb) > .16) rgb = rgb.map(value => Math.floor(value * .94))
  return `rgb(${rgb.join(',')})`
}

export async function createProfileQr(url, themeId) {
  const { default: QRCode } = await import('qrcode')
  const { default: alignmentPattern } = await import('qrcode/lib/core/alignment-pattern.js')
  const palette = themes.find(item => item.id === themeId) || themes[0]
  const primary = scanColor(palette.colors[2])
  const accent = scanColor(palette.colors[4])
  const ink = scanColor(palette.group === 'dark' ? palette.colors[2] : palette.colors[5])
  const { modules, version } = QRCode.create(url, { errorCorrectionLevel: 'H' })
  const alignment = alignmentPattern.getPositions(version)
  const size = modules.size
  const unit = 12, margin = 4
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = (size + margin * 2) * unit
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = '#fff'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.translate(margin * unit, margin * unit)
  const gradient = ctx.createLinearGradient(0, 0, size * unit, size * unit)
  gradient.addColorStop(0, ink); gradient.addColorStop(.5, primary); gradient.addColorStop(1, accent)
  ctx.fillStyle = gradient
  const finder = (row, col) => (row < 7 && col < 7) || (row < 7 && col >= size - 7) || (row >= size - 7 && col < 7)
  for (let row = 0; row < size; row++) {
    for (let col = 0; col < size; col++) {
      if (!modules.get(row, col) || finder(row, col) || alignment.some(([r, c]) => Math.abs(row - r) <= 2 && Math.abs(col - c) <= 2)) continue
      // Reserved runs must remain connected through their module centers.
      // Rounded corners remove hard square points without breaking those runs.
      ctx.beginPath()
      if (modules.isReserved(row, col)) ctx.roundRect(col * unit, row * unit, unit, unit, unit * .4)
      else ctx.arc((col + .5) * unit, (row + .5) * unit, unit * .46, 0, Math.PI * 2)
      ctx.fill()
    }
  }
  function rounded(x, y, width, radius, color) {
    ctx.fillStyle = color
    ctx.beginPath(); ctx.roundRect(x * unit, y * unit, width * unit, width * unit, radius * unit); ctx.fill()
  }
  for (const [row, col] of alignment) {
    rounded(col - 2, row - 2, 5, .8, ink)
    rounded(col - 1, row - 1, 3, .4, '#fff')
    rounded(col, row, 1, .5, accent)
  }
  for (const [x, y] of [[0, 0], [size - 7, 0], [0, size - 7]]) {
    rounded(x, y, 7, 1.7, ink)
    rounded(x + 1, y + 1, 5, 1.05, '#fff')
    rounded(x + 2, y + 2, 3, .7, accent)
  }
  // Keep the enlarged book and clear a separate white margin around it.
  // H correction and decoding tests guard the central data it covers.
  const badge = Math.max(7, Math.floor(size * .18))
  const start = (size - badge) / 2
  const padding = .9
  rounded(start - padding, start - padding, badge + padding * 2, 1.5, '#fff')
  ctx.save()
  ctx.translate(start * unit, start * unit)
  ctx.scale(badge * unit / 100, badge * unit / 100)
  ctx.translate(50, 44); ctx.scale(1.3225, 1.3225); ctx.translate(-50, -44)
  ctx.strokeStyle = ink; ctx.fillStyle = primary; ctx.lineWidth = 4.5; ctx.lineJoin = 'round'
  ctx.beginPath(); ctx.moveTo(50, 80); ctx.bezierCurveTo(37, 68, 21, 66, 12, 67); ctx.lineTo(12, 31); ctx.bezierCurveTo(25, 29, 39, 34, 50, 44); ctx.bezierCurveTo(61, 34, 75, 29, 88, 31); ctx.lineTo(88, 67); ctx.bezierCurveTo(75, 66, 61, 70, 50, 80); ctx.stroke()
  ctx.beginPath(); ctx.moveTo(47, 67); ctx.bezierCurveTo(37, 58, 28, 55, 21, 55); ctx.lineTo(21, 24); ctx.bezierCurveTo(32, 24, 41, 29, 47, 36); ctx.closePath(); ctx.fill()
  ctx.fillStyle = accent
  ctx.beginPath(); ctx.moveTo(53, 67); ctx.bezierCurveTo(63, 58, 72, 55, 79, 55); ctx.lineTo(79, 24); ctx.bezierCurveTo(68, 24, 59, 29, 53, 36); ctx.closePath(); ctx.fill()
  ctx.fillStyle = accent
  ctx.beginPath(); ctx.moveTo(50, 6); ctx.quadraticCurveTo(52, 17, 61, 19); ctx.quadraticCurveTo(52, 21, 50, 31); ctx.quadraticCurveTo(48, 21, 39, 19); ctx.quadraticCurveTo(48, 17, 50, 6); ctx.fill()
  ctx.restore()
  return canvas.toDataURL('image/png')
}
