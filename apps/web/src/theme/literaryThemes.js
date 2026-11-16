import specifications from './literaryThemes.json'
import assetDetails from './literaryThemeAssets.json'
import { themeColorRoles } from './themeColorRoles'
import { referenceThemeArtwork } from './referenceThemeArtwork'

export const literaryThemes = specifications.map(({ id,name,group,colors }) => ({
  id,name,group,colors,pack:'literary',
  art:referenceThemeArtwork[id] || (assetDetails[id] ? { banner:`/images/themes/${id}/banner.webp`, sidebar:`/images/themes/${id}/sidebar-decoration.webp`, corner:`/images/themes/${id}/corner.webp` } : null),
}))
export const literaryTokenNames = [...Object.keys(themeColorRoles(literaryThemes[0])), '--universe-banner','--universe-sidebar','--universe-corner','--universe-banner-ratio']
export function applyLiteraryTokens(root,theme) {
  for (const name of literaryTokenNames) root.style.removeProperty(name)
  if (theme.pack !== 'literary') {
    delete root.dataset.themePack
    delete root.dataset.themeMode
    return
  }
  root.dataset.themePack = 'literary'
  root.dataset.themeMode = theme.group
  const dimensions = assetDetails[theme.id]?.banner
  const tokens = {
    ...themeColorRoles(theme),
    '--universe-banner':theme.art ? `url("${theme.art.banner}")` : 'none',
    '--universe-sidebar':theme.art ? `url("${theme.art.sidebar}")` : 'none',
    '--universe-corner':theme.art ? `url("${theme.art.corner}")` : 'none',
    '--universe-banner-ratio':dimensions ? `${dimensions.width} / ${dimensions.height}` : '3 / 1',
  }
  for (const [name,value] of Object.entries(tokens)) root.style.setProperty(name,value)
}
