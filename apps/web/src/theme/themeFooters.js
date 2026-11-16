// Each theme has independent corner and repeating horizontal illustrations.
// The completed Sirenas / Aquelarre corners retain their approved artwork.
export function getThemeFooterAssets(themeId) {
  if(themeId==='canto-sirenas') return {
    corner:'/images/themes/canto-sirenas/corner-v2.png',
    strip:'/images/themes/canto-sirenas/footer-strip-v1.png',
  }
  return {
    corner:themeId==='aquelarre-medianoche' ? '/images/themes/aquelarre-medianoche/corner-v2.png' : `/images/theme-footers-v2/${themeId}/corner.webp`,
    strip:`/images/theme-footers-v2/${themeId}/strip.webp`,
  }
}

export function applyThemeFooter(root,themeId) {
  const {corner,strip}=getThemeFooterAssets(themeId)
  root.style.setProperty('--theme-footer-corner',`url("${corner}")`)
  root.style.setProperty('--theme-footer-strip',`url("${strip}")`)
}
