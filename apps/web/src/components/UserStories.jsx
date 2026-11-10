import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronLeft, ChevronRight, Pause, Play, Plus, Trash2, X } from 'lucide-react'
import { apiAssetUrl, apiRequest } from '../api/client'
import { useAuth } from '../context/AuthContext'
import './UserStories.css'

const auth = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })
const changed = () => window.dispatchEvent(new Event('libria:stories-changed'))
const activeGroups = groups => groups.map(group => ({ ...group, stories: group.stories.filter(story => new Date(story.expires_at).getTime() > Date.now()) })).filter(group => group.stories.length)

function useStories(audience, sessionKey) {
  const [data, setData] = useState({ items: [], loading: true, error: '' })
  useEffect(() => {
    let controller
    const refresh = () => {
      controller?.abort()
      controller = new AbortController()
      const signal = controller.signal
      apiRequest(`/stories?audience=${audience}`, { headers: auth(), signal })
        .then(result => { if (!signal.aborted) setData({ items: activeGroups(result.items || []), loading: false, error: '' }) })
        .catch(error => { if (!signal.aborted) setData({ items: [], loading: false, error: error.message }) })
    }
    refresh()
    const timer = setInterval(refresh, 60000)
    window.addEventListener('libria:stories-changed', refresh)
    window.addEventListener('focus', refresh)
    return () => { controller?.abort(); clearInterval(timer); window.removeEventListener('libria:stories-changed', refresh); window.removeEventListener('focus', refresh) }
  }, [audience, sessionKey])
  return data
}

function Avatar({ person }) {
  const [failed, setFailed] = useState(null)
  return person.avatar_url && failed !== person.avatar_url ? <img src={apiAssetUrl(person.avatar_url)} alt="" onError={() => setFailed(person.avatar_url)} /> : <span>{person.display_name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('')}</span>
}

// Fixed positions keep the fine dust stable through rerenders and read-state updates.
const storyRingDust = Array.from({ length: 112 }, (_, index) => {
  const angle = index * 2.399963
  const radius = 44.5 + Math.sin(index * 7.13) * 3.8 + (index % 9 === 0 ? 3 : 0)
  return { x: 50 + Math.cos(angle) * radius, y: 50 + Math.sin(angle) * radius,
    radius: .15 + ((index * 17) % 11) / 25, opacity: .25 + (index % 7) / 10 }
})

function StoryAura({ group }) {
  if (!group) return null
  const unread = group.stories.some(story => !story.seen)
  return <svg className={`story-star-ring ${unread ? 'is-unseen' : 'is-seen'}`} viewBox="0 0 100 100" aria-hidden="true">
    <circle className="story-ring-halo" cx="50" cy="50" r="44.5" />
    <g className="story-ring-dust">{storyRingDust.map((dot, index) => <circle key={index} cx={dot.x} cy={dot.y} r={dot.radius} opacity={dot.opacity} />)}</g>
    <g className="story-ring-lines">
      <circle className="story-ring-outline" cx="50" cy="50" r="44.5" />
      <ellipse className="story-ring-filament" cx="50" cy="50" rx="45.2" ry="43.8" transform="rotate(-24 50 50)" />
      <circle className="story-ring-core" cx="50" cy="50" r="44.1" />
    </g>
    <g className="story-ring-orbit">
      <circle className="story-ring-trail" cx="50" cy="50" r="44.5" transform="rotate(205 50 50)" />
      <g className="story-ring-flare" transform="translate(18.53 18.53)">
        <circle className="story-ring-flare-glow" r="3.6" />
        <path d="M-5 0Q-.6-.6 0-5Q.6-.6 5 0Q.6.6 0 5Q-.6.6-5 0Z" />
        <circle r="1" />
      </g>
      <g className="story-ring-flare story-ring-flare-small" transform="translate(81.47 81.47)">
        <circle className="story-ring-flare-glow" r="2.4" />
        <path d="M-3 0Q-.4-.4 0-3Q.4-.4 3 0Q.4.4 0 3Q-.4.4-3 0Z" />
      </g>
    </g>
  </svg>
}

function StoryDialog({ children, onClose, label, className = '' }) {
  const ref = useRef(null)
  useEffect(() => {
    const node = ref.current, opener = document.activeElement, overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    node.showModal()
    return () => { node.close(); document.body.style.overflow = overflow; if (opener?.isConnected) opener.focus({ preventScroll: true }) }
  }, [])
  return createPortal(<dialog ref={ref} className={`user-story-dialog ${className}`} aria-label={label} onCancel={event => { event.preventDefault(); onClose() }} onClick={event => { if (event.target === event.currentTarget) onClose() }}>{children}</dialog>, document.body)
}

function StoryViewer({ groups, start, onClose }) {
  const [items, setItems] = useState(() => activeGroups(groups).flatMap(group => group.stories.map(story => ({ ...story, person: group }))))
  const [index, setIndex] = useState(() => Math.max(0, items.findIndex(story => story.person.profile_id === start)))
  const [paused, setPaused] = useState(false)
  const [hidden, setHidden] = useState(document.hidden)
  const [elapsed, setElapsed] = useState(0)
  const [image, setImage] = useState(null)
  const [loadedId, setLoadedId] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const touch = useRef(null)
  const story = items[index]
  const move = useCallback(direction => {
    setIndex(current => Math.max(0, current + direction))
    setElapsed(0); setError(''); setConfirmDelete(false)
  }, [])
  useEffect(() => {
    if (!story) { onClose(); return }
    const controller = new AbortController()
    let objectUrl
    apiRequest(`/stories/${story.id}/image`, { headers: auth(), signal: controller.signal, responseType: 'blob' })
      .then(blob => { if (!controller.signal.aborted) { objectUrl = URL.createObjectURL(blob); setImage({ id: story.id, url: objectUrl }) } })
      .catch(cause => { if (!controller.signal.aborted) setError(cause.message) })
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [story, onClose])
  useEffect(() => {
    const key = event => {
      if (event.key === 'ArrowRight') move(1)
      if (event.key === 'ArrowLeft') move(-1)
      if (event.code === 'Space' && event.target.tagName !== 'BUTTON') { event.preventDefault(); setPaused(value => !value) }
    }
    const visibility = () => setHidden(document.hidden)
    document.addEventListener('keydown', key)
    document.addEventListener('visibilitychange', visibility)
    return () => { document.removeEventListener('keydown', key); document.removeEventListener('visibilitychange', visibility) }
  }, [move])
  const ready = image?.id === story?.id
  useEffect(() => {
    if (!story || loadedId !== story.id || hidden) return
    const controller = new AbortController()
    apiRequest(`/stories/${story.id}/view`, { method: 'PUT', headers: auth(), signal: controller.signal })
      .then(() => { if (!controller.signal.aborted) changed() })
      .catch(() => { /* A failed acknowledgement leaves the story unread. */ })
    return () => controller.abort()
  }, [story, loadedId, hidden])
  useEffect(() => {
    if (!story) return
    const timer = setInterval(() => {
      if (new Date(story.expires_at).getTime() <= Date.now()) { move(1); changed(); return }
      if (ready && loadedId === story.id && !paused && !hidden && !error && !confirmDelete) setElapsed(value => value + 100)
    }, 100)
    return () => clearInterval(timer)
  }, [story, ready, loadedId, paused, hidden, error, confirmDelete, move])
  useEffect(() => { if (elapsed >= 7000) move(1) }, [elapsed, move])
  if (!story) return null
  const siblings = items.filter(item => item.person.profile_id === story.person.profile_id)
  async function remove() {
    setBusy(true); setError('')
    try {
      await apiRequest(`/stories/${story.id}`, { method: 'DELETE', headers: auth() })
      setItems(current => current.filter(item => item.id !== story.id))
      setElapsed(0); setConfirmDelete(false); changed()
    } catch (cause) { setError(cause.message) }
    finally { setBusy(false) }
  }
  return <StoryDialog label={`Historias de ${story.person.display_name}`} onClose={onClose} className="user-story-viewer">
    <div className="user-story-stage" onTouchStart={event => { touch.current = { x: event.touches[0].clientX, y: event.touches[0].clientY } }} onTouchEnd={event => {
      if (!touch.current) return
      const dx = event.changedTouches[0].clientX - touch.current.x, dy = event.changedTouches[0].clientY - touch.current.y
      if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy)) move(dx < 0 ? 1 : -1)
      touch.current = null
    }}>
      {ready && <img className="user-story-image" src={image.url} alt={`Historia de ${story.person.display_name}`} onLoad={() => setLoadedId(story.id)} onError={() => setError('No se pudo mostrar esta imagen. Puedes pasar a la siguiente historia.')} />}
      <header className="user-story-toolbar">
        <div className="user-story-progress" aria-label={`Historia ${siblings.findIndex(item => item.id === story.id) + 1} de ${siblings.length}`}>{siblings.map(item => <span key={item.id}><i style={{ width: `${items.indexOf(item) < index ? 100 : item.id === story.id ? Math.min(100, elapsed / 70) : 0}%` }} /></span>)}</div>
        <div className="user-story-heading"><div className="user-story-mini-avatar"><Avatar person={story.person} /></div><strong>{story.person.display_name}</strong><button aria-label={paused ? 'Reanudar historias' : 'Pausar historias'} onClick={() => setPaused(value => !value)}>{paused ? <Play /> : <Pause />}</button>{story.person.is_owner && <button aria-label="Eliminar historia" onClick={() => setConfirmDelete(true)}><Trash2 /></button>}<button aria-label="Cerrar historias" onClick={onClose}><X /></button></div>
      </header>
      {!ready && !error && <p className="user-story-message" role="status">Cargando historia…</p>}
      {error && <p className="user-story-message" role="alert">{error}</p>}
      <button className="user-story-prev" aria-label="Historia anterior" disabled={index === 0} onClick={() => move(-1)}><ChevronLeft /></button>
      <button className="user-story-next" aria-label="Siguiente historia" onClick={() => move(1)}><ChevronRight /></button>
      <footer className="user-story-footer">{index + 1} / {items.length} · Desliza para seguir descubriendo</footer>
      {confirmDelete && <div className="user-story-confirm"><p>¿Eliminar esta historia?</p><button disabled={busy} onClick={remove}>{busy ? 'Eliminando…' : 'Eliminar'}</button><button disabled={busy} onClick={() => setConfirmDelete(false)}>Cancelar</button></div>}
    </div>
  </StoryDialog>
}

function StoryComposer({ onClose }) {
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const generation = useRef(0)
  useEffect(() => () => { generation.current++ }, [])
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url) }, [preview])
  async function select(event) {
    const file = event.target.files?.[0], version = ++generation.current
    setPreview(null); setError('')
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) { setError('Selecciona una imagen JPEG, PNG o WebP de hasta 5 MB.'); return }
    setBusy(true)
    try {
      const bitmap = await createImageBitmap(file)
      if (bitmap.width * bitmap.height > 25000000) { bitmap.close(); throw new Error('Imagen demasiado grande') }
      const canvas = document.createElement('canvas')
      canvas.width = 1080; canvas.height = 1920
      const context = canvas.getContext('2d')
      context.fillStyle = '#181522'; context.fillRect(0, 0, 1080, 1920)
      const scale = Math.min(1080 / bitmap.width, 1920 / bitmap.height)
      context.drawImage(bitmap, (1080 - bitmap.width * scale) / 2, (1920 - bitmap.height * scale) / 2, bitmap.width * scale, bitmap.height * scale)
      bitmap.close()
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.9))
      if (!blob) throw new Error('No se pudo preparar la imagen.')
      if (generation.current === version) setPreview({ blob, url: URL.createObjectURL(blob) })
    } catch { if (generation.current === version) setError('No se pudo abrir esta imagen. Selecciona otra.') }
    finally { if (generation.current === version) setBusy(false) }
  }
  async function publish() {
    setBusy(true); setError('')
    try {
      await apiRequest('/stories', { method: 'POST', headers: { ...auth(), 'Content-Type': 'image/jpeg' }, body: preview.blob })
      changed(); onClose()
    } catch (cause) { setError(cause.message); setBusy(false) }
  }
  return <StoryDialog label="Publicar una historia" onClose={() => { if (!busy) onClose() }} className="user-story-composer">
    <header><h2>Tu historia entre libros</h2><button aria-label="Cerrar publicación de historia" disabled={busy} onClick={onClose}><X /></button></header>
    <p>Comparte una imagen durante 24 horas. Sigue la privacidad de tu perfil.</p>
    <label className="user-story-file">Seleccionar imagen<input type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={select} /></label>
    <small>JPEG, PNG o WebP · Hasta 5 MB · Formato vertical 9:16</small>
    {preview && <img className="user-story-preview" src={preview.url} alt="Vista previa de tu historia en formato 9:16" />}
    {error && <p role="alert">{error}</p>}
    <button className="user-story-publish" disabled={!preview || busy} onClick={publish}>{busy ? 'Preparando historia…' : 'Publicar por 24 horas'}</button>
  </StoryDialog>
}

export function ProfileStoryAvatar({ user, publicView }) {
  const data = useStories('community', user.id)
  const [view, setView] = useState(null)
  const [composing, setComposing] = useState(false)
  const closeView = useCallback(() => setView(null), [])
  const group = data.items.find(item => publicView ? item.profile_id === user.id : item.is_owner)
  const owner = !publicView || user.is_owner
  return <><div className="profile-story-controls"><button className={`reader-profile-avatar profile-story-avatar ${group ? 'has-stories' : ''}`} aria-label={group ? `Ver historias de ${user.display_name}` : owner ? 'Publicar una historia' : `${user.display_name} no tiene historias activas`} disabled={!group && !owner} onClick={() => group ? setView({ groups: data.items, start: group.profile_id }) : setComposing(true)}><span className="story-avatar-photo"><Avatar person={user} /></span><StoryAura group={group} /></button>{owner && <button className="profile-story-add" aria-label="Agregar historia" onClick={() => setComposing(true)}><Plus size={16} /></button>}</div>
    {view && <StoryViewer groups={view.groups} start={view.start} onClose={closeView} />}
    {composing && <StoryComposer onClose={() => setComposing(false)} />}
  </>
}

export default function UserStories() {
  const { user } = useAuth()
  const data = useStories('contacts', user.id)
  const [view, setView] = useState(null)
  const [composing, setComposing] = useState(false)
  const closeView = useCallback(() => setView(null), [])
  const ownGroup = data.items.find(person => person.is_owner)
  return <section className="user-stories" aria-labelledby="user-stories-title"><h2 id="user-stories-title">Historias de usuarios</h2><p>Pequeños momentos de nuestra comunidad lectora.</p>
    <div className="user-stories-row"><div className="user-story-own"><button className="user-story-person" aria-label={ownGroup ? 'Ver mis historias' : 'Publicar mi primera historia'} onClick={() => ownGroup ? setView({ groups: data.items, start: ownGroup.profile_id }) : setComposing(true)}><span className={`user-story-avatar ${ownGroup ? 'has-stories' : ''}`}><span className="story-avatar-photo"><Avatar person={user} /></span><StoryAura group={ownGroup} /></span><span>Tu historia</span></button><button className="user-story-add" aria-label="Agregar historia desde contactos" onClick={() => setComposing(true)}><Plus size={16} /></button></div>
      {data.items.filter(person => !person.is_owner).map(person => <button key={person.profile_id} className="user-story-person" aria-label={`Ver historias de ${person.display_name}`} onClick={() => setView({ groups: data.items, start: person.profile_id })}><span className="user-story-avatar has-stories"><span className="story-avatar-photo"><Avatar person={person} /></span><StoryAura group={person} /></span><span>{person.display_name}</span></button>)}
    </div>{data.loading && <p role="status">Cargando historias…</p>}{data.error && <p role="alert">{data.error} <button onClick={changed}>Reintentar</button></p>}{!data.loading && !data.error && !data.items.length && <p>Aún no hay historias de tus contactos. Comparte la primera.</p>}
    {view && <StoryViewer groups={view.groups} start={view.start} onClose={closeView} />}
    {composing && <StoryComposer onClose={() => setComposing(false)} />}
  </section>
}
