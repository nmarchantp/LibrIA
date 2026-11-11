export default function InfluencerApplicationDetails({ request }) {
  return <div>
    {request.activity_description && <p><strong>Actividad literaria:</strong> {request.activity_description}</p>}
    {request.topics?.length > 0 && <p><strong>Temáticas:</strong> {request.topics.join(', ')}</p>}
    <p><strong>Motivación:</strong> {request.motivation || request.note}</p>
    {request.evidence_links?.length > 0 && <ul>{request.evidence_links.map(url => <li key={url}><a href={url} target="_blank" rel="noopener noreferrer">{url}</a></li>)}</ul>}
    {request.decided_at && <p><strong>Evaluación:</strong> {new Date(request.decided_at).toLocaleString('es-CL')} · {request.decided_by_name || request.decided_by_user_id || 'Administración'}<br />{request.decision_reason || 'Decisión histórica sin observación independiente.'}</p>}
  </div>
}
