import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import ProfileEditModal from './ProfileEditModal'
import ModerationContent, { ModerationAttachments } from './ModerationContent'
import { kindLabels, statusLabels, moderationError, moderationRequest } from '../services/moderation'
import './Moderation.css'

export default function PrivateModerationStatus({ userId }) {
  const [params] = useSearchParams()
  const [data, setData] = useState(null), [offset, setOffset] = useState(0), [epoch, setEpoch] = useState(0)
  const [error, setError] = useState(''), [detail, setDetail] = useState(null)
  const revision = params.get('revision')
  useEffect(() => {
    const controller = new AbortController()
    moderationRequest(`/me/moderation?limit=10&offset=${offset}`, { signal: controller.signal }).then(value => { if (!controller.signal.aborted) setData(value) })
      .catch(cause => { if (!controller.signal.aborted) setError(moderationError(cause)) })
    return () => controller.abort()
  }, [userId, offset, epoch])
  useEffect(() => {
    const refresh = () => setEpoch(value => value + 1)
    window.addEventListener('libria:moderation-pending', refresh); window.addEventListener('libria:moderation-changed', refresh)
    return () => { window.removeEventListener('libria:moderation-pending', refresh); window.removeEventListener('libria:moderation-changed', refresh) }
  }, [])
  useEffect(() => {
    if (!revision) return
    const controller = new AbortController()
    moderationRequest(`/me/moderation/${revision}`, { signal: controller.signal }).then(value => { if (!controller.signal.aborted) setDetail(value) })
      .catch(cause => { if (!controller.signal.aborted) setError(moderationError(cause)) })
    return () => controller.abort()
  }, [revision, userId])
  async function open(id) {
    setError('')
    try { setDetail(await moderationRequest(`/me/moderation/${id}`)) } catch (cause) { setError(moderationError(cause)) }
  }
  return <section className="private-moderation-list" aria-labelledby="private-moderation-title"><h2 id="private-moderation-title">Estado de publicaciones</h2><p>Esta información solo es visible para ti.</p>
    {error && <p role="alert">{error} <button type="button" onClick={() => { setError(''); setEpoch(value => value + 1) }}>Reintentar</button></p>}
    {!data && !error && <p role="status">Cargando estados…</p>}
    {data && <>{!data.items.length && <p>No tienes contenidos enviados a moderación.</p>}{data.items.map(item => <article key={item.id}><span>{kindLabels[item.kind]} · {statusLabels[item.status]}{item.lifecycle !== 'active' && ` · ${statusLabels[item.lifecycle]}`}</span><h3>{item.title || item.excerpt || kindLabels[item.kind]}</h3><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString('es-CL')}</time>{item.decision_reason && <p>Motivo: {item.decision_reason}</p>}<button type="button" className="button" onClick={() => open(item.id)}>Ver detalle privado</button></article>)}<div className="moderation-pagination"><button disabled={!offset} onClick={() => setOffset(value => Math.max(0, value - 10))}>Anterior</button><button disabled={!data.has_more} onClick={() => setOffset(value => value + 10)}>Siguiente</button></div></>}
    <ProfileEditModal open={Boolean(detail)} title="Estado de tu contenido" description={detail ? `${statusLabels[detail.status]}${detail.lifecycle !== 'active' ? ` · ${statusLabels[detail.lifecycle]}` : ''}` : ''} saveDisabled saveLabel="Solo lectura" onClose={() => setDetail(null)} onSubmit={event => event.preventDefault()}>
      {detail && <>{detail.decision_reason && <p>Motivo de la decisión: {detail.decision_reason}</p>}<ModerationContent content={detail.proposal} label="Contenido enviado"><ModerationAttachments assets={detail.attachments} /></ModerationContent></>}
    </ProfileEditModal>
  </section>
}
