// Deterministic sRGB roles: keep the authored palette, derive readable UI colors.
export function mixColor(a, b, amount) {
  const channels = color => color.slice(1).match(/../g).map(value => parseInt(value, 16))
  return '#' + channels(a).map((v, i) => Math.round(v * amount + channels(b)[i] * (1 - amount)).toString(16).padStart(2, '0')).join('').toUpperCase()
}
export function contrastRatio(a, b) {
  const luminance = color => color.slice(1).match(/../g).map(v => parseInt(v, 16) / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((sum, v, i) => sum + v * [.2126,.7152,.0722][i], 0)
  const x = luminance(a), y = luminance(b)
  return (Math.max(x, y) + .05) / (Math.min(x, y) + .05)
}
function readable(foreground, toward, backgrounds, minimum) {
  for (let n = 0; n <= 100; n++) {
    const candidate = mixColor(toward, foreground, n / 100)
    if (backgrounds.every(bg => contrastRatio(candidate, bg) >= minimum)) return candidate
  }
  return toward
}
export function themeColorRoles({ colors, group }) {
  const [paper,surface,primary,secondary,accent,ink] = colors
  const dark = group === 'dark'
  const soft = mixColor(secondary,surface,.35)
  const field = mixColor(paper,surface,.5)
  const neutralHover = mixColor(secondary,surface,.55)
  const onPrimary = contrastRatio(primary,'#FFFFFF') >= 4.5 ? '#FFFFFF' : contrastRatio(primary,'#101217') >= 4.5 ? '#101217' : '#000000'
  const control = readable(mixColor(ink,surface,.35),ink,[field,soft,neutralHover,surface],3.25)
  const link = readable(primary,ink,[surface,paper,soft,neutralHover],4.6)
  return {
    '--muted':readable(mixColor(ink,surface,.78),ink,[surface,paper,soft,neutralHover],4.6),
    '--line':mixColor(ink,surface,.3), '--panel-border':mixColor(ink,surface,.24),
    '--soft':soft, '--surface-raised':mixColor(surface,'#FFFFFF',dark ? .93 : .6),
    '--field-bg':field, '--control-border':control, '--focus':link,
    '--button-bg':primary, '--on-primary':onPrimary,
    '--primary-hover':readable(mixColor(primary,dark ? '#FFFFFF' : ink,.88),onPrimary === '#FFFFFF' ? '#000000' : '#FFFFFF',[onPrimary],4.6),
    '--accent-text':link, '--neutral-button-bg':soft, '--neutral-button-hover':neutralHover,
    '--sidebar-bg':mixColor(paper,surface,.6), '--orange':link, '--lavender-soft':soft,
    '--on-feature':ink, '--feature-start':soft, '--feature-end':paper,
    '--shadow-color':dark ? '#00000040' : '#18202C1A',
    '--universe-accent':readable(accent,ink,[paper,surface],3.1),
  }
}
