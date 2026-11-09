import { useRef, useState } from 'react'
import { Flag } from 'lucide-react'
import ProfileEditModal from './ProfileEditModal'
import { useAuth } from '../context/AuthContext'
import { moderationError, moderationRequest, reasonLabels } from '../services/moderation'
import './Moderation.css'

export default function ContentReportButton({ kind, identifier, menu = false }) {
  const { user } = useAuth()
  const [open, setOpen] = useState(false), [reason, setReason] = useState(''), [detail, setDetail] = useState('')
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [sent, setSent] = useState(false)
  const sending = useRef(false)
  if (!user || !identifier || !['publication', 'review', 'comment'].includes(kind)) return null
  async function submit(event) {
    event.preventDefault()
    if (sending.current || !reason) return
    sending.current = true; setBusy(true); setError('')
    try {
      await moderationRequest(`/content-reports/${kind}/${identifier}`, { method: 'POST', body: JSON.stringify({ reason, detail: detail.trim() }) })
      setSent(true); setOpen(false)
    } catch (cause) { setError(moderationError(cause)) }
    finally { sending.current = false; setBusy(false) }
  }
  return <><button type="button" className={menu ? undefined : 'moderation-report-button'} disabled={sent} onClick={event => {
    event.stopPropagation(); const parent = event.currentTarget.closest('details'); if (parent) parent.open = false
    setError(''); setOpen(true)
  }}><Flag size={14} aria-hidden="true" />{sent ? 'Reporte enviado' : 'Reportar'}</button>
    {sent && <span className="moderation-report-status" role="status">Reporte recibido. Gracias por ayudarnos a cuidar la comunidad.</span>}
    <ProfileEditModal open={open} title="Reportar contenido" icon={<Flag size={21} />} description="Un administrador revisará tu reporte. El contenido no se oculta automáticamente."
      busy={busy} saveLabel="Enviar reporte" saveDisabled={!reason} dirty={Boolean(detail || reason)} onClose={() => setOpen(false)} onSubmit={submit}>
      <label>Motivo<select required value={reason} onChange={event => setReason(event.target.value)}><option value="">Selecciona un motivo</option>{Object.entries(reasonLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label>Descripción opcional<textarea rows={3} maxLength={2000} value={detail} onChange={event => setDetail(event.target.value)} /></label>
      {error && <p role="alert">{error}</p>}
    </ProfileEditModal>
  </>
}
