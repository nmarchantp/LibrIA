import { useEffect, useRef, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import ProfileEditModal from './ProfileEditModal'
import ModerationContent, { ModerationAttachments } from './ModerationContent'
import { kindLabels, statusLabels, reasonLabels, categoryLabels, moderationError, moderationRequest } from '../services/moderation'
import './Moderation.css'

const date = value => new Date(value).toLocaleString('es-CL')
const actionLabels = { approved: 'Aprobar', rejected: 'Rechazar', dismissed: 'Descartar reporte', hidden: 'Ocultar preventivamente', restored: 'Restituir contenido' }

function ReviewDialog({ selection, onClose, onChanged }) {
  const [data, setData] = useState(selection.history || null), [error, setError] = useState('')
  const [action, setAction] = useState(''), [reason, setReason] = useState(''), [busy, setBusy] = useState(false), [epoch, setEpoch] = useState(0)
  const sending = useRef(false), intent = useRef(null)
  const report = selection.tab === 'reports', readonly = selection.tab === 'history'
  useEffect(() => {
    if (readonly) return
    const controller = new AbortController()
    moderationRequest(`/admin/moderation/${report ? 'reports/' : ''}${selection.id}`, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setData(value) }).catch(cause => { if (!controller.signal.aborted) setError(moderationError(cause)) })
    return () => controller.abort()
  }, [selection.id, report, readonly, epoch])
  async function submit(event) {
    event.preventDefault()
    if (sending.current || !action || !reason.trim() || !data) return
    sending.current = true; setBusy(true); setError('')
    const payload = { action, reason: reason.trim(), expected_version: report ? data.current_content.moderation_version : data.base_version }
    const signature = JSON.stringify(payload)
    if (intent.current?.signature !== signature) intent.current = { signature, key: crypto.randomUUID() }
    try {
      await moderationRequest(`/admin/moderation/${report ? `reports/${data.id}/resolution` : `${data.id}/decision`}`, { method: 'POST', headers: { 'Idempotency-Key': intent.current.key }, body: signature })
      onChanged(`${actionLabels[action]}: decisión guardada.`)
    } catch (cause) {
      setError(moderationError(cause))
      if ([403, 404, 409].includes(cause.status)) { setAction(''); setReason(''); setData(null); setEpoch(value => value + 1); onChanged(null) }
    } finally { sending.current = false; setBusy(false) }
  }
  const mediaBase = data?.kind === 'publication' ? `/admin/moderation/content/publication/${data.content_id}` : undefined
  return <ProfileEditModal open title={readonly ? 'Detalle del historial' : report ? 'Revisar reporte' : 'Revisar contenido'} icon={<ShieldCheck size={22} />} description="La decisión y su motivo quedarán registrados en el historial."
    className="moderation-review-dialog" busy={busy} dirty={Boolean(reason)} saveDisabled={readonly || !data || !action || !reason.trim()} saveLabel={action ? `Confirmar: ${actionLabels[action].toLowerCase()}` : 'Selecciona una acción'} onClose={onClose} onSubmit={submit}>
    {error && <p role="alert">{error}</p>}
    {!data && <p role="status">Cargando contenido…</p>}
    {data && (readonly ? <><p>{data.administrator} · {date(data.created_at)}</p><p>{data.reason}</p><div className="moderation-comparison"><ModerationContent label="Versión anterior" content={data.context?.previous} /><ModerationContent label="Resultado" content={data.context?.result} /></div></> : <>
      <p><strong>{data.author}</strong> · {kindLabels[data.kind]} · {statusLabels[data.status]}</p>
      {report ? <><p>{reasonLabels[data.reason]} · {data.report_count} reporte(s)</p><p className="moderation-full-text">{data.detail}</p><div className="moderation-comparison"><ModerationContent label="Contenido reportado" content={data.reported_content} /><ModerationContent label="Contenido actual" content={data.current_content} mediaBase={mediaBase} /></div></> : <>
        <ul>{data.findings.map((finding, i) => <li key={i}><strong>{categoryLabels[finding.category] || finding.category}</strong>: {finding.reason}</li>)}</ul>
        <div className="moderation-comparison"><ModerationContent label="Versión pública anterior" content={data.public_version} mediaBase={data.public_version ? mediaBase : undefined} /><ModerationContent label="Propuesta pendiente" content={data.proposal} mediaBase={data.public_version ? undefined : mediaBase}><ModerationAttachments assets={data.attachments} /></ModerationContent></div>
      </>}
      <fieldset className="moderation-action-picker" disabled={busy}><legend>Decisión administrativa</legend>{(report ? data.status === 'pending' ? ['dismissed', 'hidden'] : data.status === 'hidden' && data.current_content?.moderation_hidden ? ['restored'] : [] : data.status === 'pending_review' && data.lifecycle === 'active' ? ['approved', 'rejected'] : []).map(value => <button key={value} type="button" aria-pressed={action === value} onClick={() => setAction(value)}>{actionLabels[value]}</button>)}</fieldset>
      {action && <label>Motivo obligatorio<textarea required maxLength={2000} rows={3} value={reason} onChange={event => setReason(event.target.value)} /><small>Confirma «{actionLabels[action]}» para aplicar esta decisión.</small></label>}
    </>)}
  </ProfileEditModal>
}

export default function ModerationSection({ initiallyOpen = false }) {
  const [tab, setTab] = useState('pending'), [reportStatus, setReportStatus] = useState('pending'), [offset, setOffset] = useState(0)
  const [data, setData] = useState(null), [counts, setCounts] = useState(null), [error, setError] = useState(''), [message, setMessage] = useState(''), [epoch, setEpoch] = useState(0)
  const [selection, setSelection] = useState(null)
  const path = tab === 'pending' ? '/admin/moderation' : tab === 'reports' ? `/admin/moderation/reports?status=${reportStatus}` : '/admin/moderation/history'
  useEffect(() => {
    const controller = new AbortController()
    setData(null); setError('')
    moderationRequest(`${path}${path.includes('?') ? '&' : '?'}limit=10&offset=${offset}`, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setData(value) }).catch(cause => { if (!controller.signal.aborted) setError(moderationError(cause)) })
    return () => controller.abort()
  }, [path, offset, epoch])
  useEffect(() => {
    const controller = new AbortController()
    moderationRequest('/admin/moderation?limit=1', { signal: controller.signal }).then(value => { if (!controller.signal.aborted) setCounts({ pending: value.total, reports: value.pending_reports }) }).catch(() => { if (!controller.signal.aborted) setCounts(null) })
    return () => controller.abort()
  }, [epoch])
  function changed(text) {
    setEpoch(value => value + 1)
    window.dispatchEvent(new Event('libria:moderation-changed'))
    if (text) { setMessage(text); setSelection(null) }
  }
  return <details className="environment-panel moderation-section" id="content-moderation" open={initiallyOpen || window.location.hash === '#content-moderation' || undefined}>
    <summary><ShieldCheck size={23} /><h2>Moderación de contenido</h2>{counts && <span className="moderation-counter" aria-label={`${counts.pending} revisiones y ${counts.reports} reportes pendientes`}>{counts.pending + counts.reports} pendientes</span>}</summary>
    <nav className="moderation-tabs" aria-label="Gestión de moderación">{[['pending', 'Pendientes de aprobación'], ['reports', 'Reportes de usuarios'], ['history', 'Historial']].map(([value, label]) => <button type="button" key={value} aria-pressed={tab === value} onClick={() => { setTab(value); setOffset(0); setMessage('') }}>{label}{value !== 'history' && counts && <span> {counts[value === 'pending' ? 'pending' : 'reports']}</span>}</button>)}</nav>
    {tab === 'reports' && <label>Estado<select value={reportStatus} onChange={event => { setReportStatus(event.target.value); setOffset(0) }}><option value="pending">Pendientes</option><option value="dismissed">Descartados</option><option value="hidden">Resueltos con ocultación</option></select></label>}
    {message && <p role="status">{message}</p>}
    {error ? <p role="alert">{error} <button type="button" onClick={() => setEpoch(value => value + 1)}>Reintentar</button></p> : !data ? <p role="status">Cargando moderación…</p> : <>
      {!data.items.length && <p className="moderation-empty">No hay elementos en esta sección.</p>}
      <div className="moderation-list">{data.items.map(item => <article key={item.id}><div><span className="kicker">{tab === 'history' ? statusLabels[item.action] : `${kindLabels[item.kind]} · ${statusLabels[item.status]}`}</span><h3>{item.title || (tab === 'history' ? item.administrator : item.author)}</h3><time dateTime={item.created_at}>{date(item.created_at)}</time>
        {tab === 'pending' && <><p>{item.author}</p>{item.findings.map((finding, index) => <p key={index}><strong>{categoryLabels[finding.category] || finding.category}</strong>: {finding.reason}</p>)}</>}
        {tab === 'reports' && <p>{reasonLabels[item.reason]} · {item.report_count} reporte(s)</p>}
        <p className="moderation-excerpt">{tab === 'history' ? item.reason : item.excerpt}</p></div>
        <button type="button" className="button" onClick={() => setSelection({ id: item.id, tab, history: tab === 'history' ? item : null })}>{tab === 'history' ? 'Ver detalle' : 'Revisar contenido'}</button></article>)}</div>
      <div className="moderation-pagination"><button type="button" disabled={!offset} onClick={() => setOffset(value => Math.max(0, value - 10))}>Anterior</button><span>{data.total} elementos</span><button type="button" disabled={!data.has_more} onClick={() => setOffset(value => value + 10)}>Siguiente</button></div>
    </>}
    {selection && <ReviewDialog key={`${selection.tab}:${selection.id}`} selection={selection} onClose={() => setSelection(null)} onChanged={changed} />}
  </details>
}
