import { useEffect, useState } from 'react'
import { moderationRequest } from '../services/moderation'

function PrivateImage({ path, label }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    let active = true, objectUrl
    const controller = new AbortController()
    moderationRequest(path, { responseType: 'blob', signal: controller.signal }).then(blob => {
      if (active) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl) }
    }).catch(() => {})
    return () => { active = false; controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [path])
  return url ? <a href={url} target="_blank" rel="noreferrer"><img src={url} alt={label} /></a> : <span>{label}: imagen no disponible</span>
}

export default function ModerationContent({ content, label, children, mediaBase }) {
  if (!content) return <section className="moderation-version"><h3>{label}</h3><p>No existe una versión pública anterior.</p></section>
  const event = content.event_details || content.event
  return <section className="moderation-version"><h3>{label}</h3>
    {content.title && <h4>{content.title}</h4>}
    <p className="moderation-full-text">{content.body}</p>
    {content.rating != null && <p>Valoración: {content.rating}/5</p>}
    {content.is_spoiler && <p>Contiene spoilers</p>}
    {content.dimension_ratings && Object.entries(content.dimension_ratings).map(([key, value]) => <p key={key}>{key}: {value}/5</p>)}
    {(content.book_title || content.work_id || content.book_ref) && <p>Obra: {content.book_title || content.work_id || content.book_ref}{content.edition_id && ` · Edición: ${content.edition_id}`}</p>}
    {event && <dl>{Object.entries(event).filter(([key, value]) => value != null && !['post_id', 'created_at', 'updated_at'].includes(key)).map(([key, value]) => <div key={key}><dt>{({ start_date: 'Inicio', start_time: 'Hora', end_date: 'Término', end_time: 'Hora de término', starts_at: 'Inicio', ends_at: 'Término', timezone: 'Zona horaria', location: 'Lugar', organizer: 'Organizador', category: 'Categoría' })[key] || key}</dt><dd>{String(value)}</dd></div>)}</dl>}
    {content.existing_image_ids && <p>Fotografías conservadas: {content.existing_image_ids.length}</p>}
    {content.cover_mode && <p>Portada: {({ keep: 'Conservar', catalog: 'Catálogo', custom: 'Personalizada' })[content.cover_mode]}</p>}
    {mediaBase && <div className="moderation-images">{content.images?.map(image => <PrivateImage key={image.id} path={`${mediaBase}/images/${image.id}`} label="Fotografía adjunta" />)}{content.cover && <PrivateImage path={`${mediaBase}/cover`} label="Portada personalizada" />}</div>}
    {children}
  </section>
}

export function ModerationAttachments({ assets = [] }) {
  return <div className="moderation-images">{assets.map(asset => <PrivateImage key={asset.id} path={asset.url} label={asset.role === 'cover' ? 'Portada propuesta' : 'Fotografía propuesta'} />)}</div>
}
