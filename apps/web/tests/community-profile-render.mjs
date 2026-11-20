import assert from 'node:assert/strict'
import { build } from 'esbuild'
import { mkdir, rm } from 'node:fs/promises'
import { pathToFileURL, fileURLToPath } from 'node:url'
import path from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const cache = path.join(root, 'node_modules', '.cache')
await mkdir(cache, { recursive: true })
const outfile = path.join(cache, 'community-profile-render.mjs')
try {
  await build({
    absWorkingDir: root, bundle: true, platform: 'node', format: 'esm', packages: 'external', jsx: 'automatic',
    outfile, loader: { '.css': 'empty' }, logLevel: 'silent',
    stdin: { resolveDir: root, loader: 'jsx', contents: `
      import React from 'react'
      import { renderToStaticMarkup } from 'react-dom/server'
      import { MemoryRouter, Routes, Route } from 'react-router-dom'
      import CommunityProfilePage from './src/pages/CommunityProfilePage.jsx'
      import ProfilePrivacySettings from './src/components/ProfilePrivacySettings.jsx'
      export function renderProfile(data, preview = false) {
        globalThis.__profileScenario = data
        return renderToStaticMarkup(<MemoryRouter initialEntries={[preview ? '/profiles/person?preview=1' : '/profiles/person']}><Routes><Route path="/profiles/:profileId" element={<CommunityProfilePage />} /></Routes></MemoryRouter>)
      }
      export function renderSettings(data, showSections = false) {
        return renderToStaticMarkup(<MemoryRouter><ProfilePrivacySettings showSections={showSections} preferences={{ data, save: async () => {} }} /></MemoryRouter>)
      }
    ` },
    plugins: [{ name: 'isolated-profile-data', setup(builder) {
      builder.onLoad({ filter: /useLiteraryPreferences\.js$/ }, () => ({ contents: 'export default function usePreferences() { return { data: globalThis.__profileScenario, loading: false, error: "", retry() {} } }', loader: 'js' }))
      builder.onLoad({ filter: /ThemeContext\.jsx$/ }, () => ({ contents: 'export const useTheme = () => ({ theme: "dark" })', loader: 'js' }))
      builder.onLoad({ filter: /api[\\/]client\.js$/ }, () => ({ contents: 'export const apiRequest = async () => ({}); export const apiAssetUrl = value => value; export const apiUrl = value => value; export const configureAuthSession = () => {}', loader: 'js' }))
    } }],
  })
  const { renderProfile, renderSettings } = await import(pathToFileURL(outfile).href)
  const base = { id: 'person', display_name: 'Otra lectora', avatar_url: '/avatar.png', profile_visibility: 'private', can_view: false, following: false, is_owner: false, follows_you: false, visible_sections: [], biography: 'Biografía protegida', favorite_quotes: ['Cita protegida'], genres: [], tropes: [], intensities: [], interests: [] }
  const locked = renderProfile(base)
  assert.match(locked, /Otra lectora/)
  assert.match(locked, /avatar\.png/)
  assert.match(locked, /reader-profile-cover/)
  assert.match(locked, /reader-profile--panoramic/)
  assert.match(locked, /reader-profile-top/)
  assert.match(locked, /reader-profile-cover--panoramic/)
  assert.match(locked, /Esta persona debe seguirte/)
  assert.match(locked, /reciba una notificación/)
  assert.doesNotMatch(locked, /Biografía protegida|Cita protegida|reader-about-grid|reader-favorite-quotes/)
  assert.match(locked, />Seguir<\/button>/)
  const following = renderProfile({ ...base, following: true })
  assert.match(following, /Dejar de seguir/)
  assert.match(following, /Ya sigues a esta persona/)
  assert.doesNotMatch(following, /Biografía protegida/)
  const publicProfile = renderProfile({ ...base, profile_visibility: 'public', can_view: true, visible_sections: ['biography'] })
  assert.match(publicProfile, /Perfil público/)
  assert.match(publicProfile, /Biografía protegida/)
  assert.doesNotMatch(publicProfile, /Cita protegida|reader-tastes-card|reader-reading-tastes/)
  assert.doesNotMatch(publicProfile, /reader-edit-button/)
  const preview = renderProfile({ ...base, is_owner: true, profile_visibility: 'public', can_view: true, visible_sections: ['biography'] }, true)
  assert.match(preview, /reader-profile-cover--panoramic/)
  assert.match(preview, /Volver a mi perfil/)
  assert.doesNotMatch(preview, /Configurar privacidad|Agregar historia|Publicar una historia|reader-edit-button|profile-story-add/)
  const unlocked = renderProfile({ ...base, can_view: true, follows_you: true, visible_sections: ['favorite_quotes'] })
  assert.match(unlocked, /Cita protegida/)
  assert.match(unlocked, /Te sigue/)
  assert.doesNotMatch(unlocked, /Biografía protegida|Este perfil es privado|reader-edit-button/)
  const empty = renderProfile({ ...base, can_view: true, profile_visibility: 'public' })
  assert.match(empty, /aún no comparte secciones/)
  const settings = renderSettings({ profile_id: 'person', profile_visibility: 'private', public_sections: ['biography'] })
  assert.match(settings, /Solo las personas a las que sigues/)
  assert.equal((settings.match(/type="checkbox"/g) || []).length, 0)
  const sharing = renderSettings({ profile_id: 'person', profile_visibility: 'public', public_sections: ['library', 'events'] }, true)
  assert.equal((sharing.match(/type="checkbox"/g) || []).length, 10)
  assert.equal((sharing.match(/checked=""/g) || []).length, 2)
  const showcase = renderProfile({ ...base, can_view: true, visible_sections: ['library', 'activity', 'analyses'] })
  assert.match(showcase, /Mi biblioteca/)
  assert.match(showcase, /Mi actividad/)
  assert.match(showcase, /Mis análisis/)
  assert.doesNotMatch(showcase, /type="checkbox"|Gestionar mi biblioteca/)
  const interests = renderProfile({ ...base, can_view: true, visible_sections: ['interests', 'favorite_quotes'], interests: [{ id: 'art', name: 'Arte', group: 'Cultura' }] })
  assert.match(interests, /Mis intereses/)
  assert.match(interests, /Arte/)
  assert.match(interests, /reader-favorite-quotes/)
  assert.doesNotMatch(interests, /Editar mis intereses|type="checkbox"/)
  console.log('PASS: private, following, public, unlocked and empty profile views; section privacy controls')
} finally {
  await rm(outfile, { force: true })
}
