import { Check, X, ClipboardCheck, Clock3 } from 'lucide-react'
import InfluencerApplicationDetails from './InfluencerApplicationDetails'

const roles = { lector: 'Lector', autor: 'Autor', influencer: 'Influencer', libreria: 'Librería', editorial: 'Editorial', admin: 'Administrador' }

export default function AdminVerificationRequests({ requests, observations, onObservation, onDecide, busy, loading, onOpenUser }) {
  return <section className="admin-requests" aria-label="Solicitudes pendientes">
    <header className="requests-heading">
      <div><h2>Solicitudes pendientes <span className="requests-count">{requests.length}</span></h2><p>Revisa los antecedentes y registra tu decisión para cada perfil.</p></div>
      <span className="requests-heading-icon" aria-hidden="true"><ClipboardCheck size={24} /></span>
    </header>
    {loading ? <p className="admin-empty" role="status">Cargando solicitudes…</p> : requests.length === 0 ? <div className="requests-empty"><ClipboardCheck size={32} aria-hidden="true" /><h3>Todo al día</h3><p>No hay solicitudes pendientes de revisión.</p></div> : requests.map(request => {
      const observation = observations[request.id] || ''
      const count = Array.from(observation.trim()).length
      const helpId = `request-help-${request.id}`
      return <article className="admin-request" key={request.id} aria-labelledby={`request-title-${request.id}`}>
        <header className="request-heading">
          <span className="request-avatar" aria-hidden="true">{request.display_name?.trim().charAt(0).toUpperCase() || '?'}</span>
          <div className="request-identity"><h3 id={`request-title-${request.id}`}>{request.display_name}</h3><p>{request.email}</p></div>
          <span className="request-pending"><Clock3 size={13} aria-hidden="true" /> Por revisar</span>
        </header>
        <div className="request-meta">{onOpenUser && <button type="button" className="button" onClick={() => onOpenUser(request)}>Abrir ficha del usuario</button>}<span>Perfil solicitado <strong>{roles[request.requested_role] || request.requested_role}</strong></span>{request.created_at && <time dateTime={request.created_at}>{new Date(request.created_at).toLocaleDateString('es-CL', { day: 'numeric', month: 'short', year: 'numeric' })}</time>}</div>
        <div className="request-body">
          <section className="request-background"><h4>Antecedentes de la solicitud</h4><InfluencerApplicationDetails request={request} /></section>
          <section className="request-decision"><h4>Decisión administrativa</h4><label htmlFor={`request-note-${request.id}`}>Observación <span>(obligatoria)</span></label><textarea id={`request-note-${request.id}`} aria-describedby={helpId} value={observation} onChange={event => onObservation(request.id, event.target.value)} minLength={10} maxLength={1000} rows={4} disabled={busy} placeholder="Explica por qué apruebas o rechazas esta solicitud…" /><div className="request-note-help" id={helpId}><span>{count < 10 ? 'Escribe al menos 10 caracteres para continuar.' : 'La observación quedará registrada con tu decisión.'}</span><span>{Array.from(observation).length}/1000</span></div>
            <div className="admin-request-actions"><button type="button" className="button primary" disabled={busy || count < 10} onClick={() => onDecide(request, 'approve')}><Check size={16} aria-hidden="true" /> Aprobar perfil</button><button type="button" className="button request-reject" disabled={busy || count < 10} onClick={() => onDecide(request, 'reject')}><X size={16} aria-hidden="true" /> Rechazar</button></div>
          </section>
        </div>
      </article>
    })}
  </section>
}
