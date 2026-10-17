import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { apiRequest } from '../api/client'
import ActionStatus from './ActionStatus'
import './CommunityDashboard.css'

const formatDate = value => new Intl.DateTimeFormat('es-CL', { dateStyle: 'medium', timeZone: 'America/Santiago' }).format(new Date(value))

export default function CommunityDashboard() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setBusy(true); setError(''); setData(null)
    apiRequest('/analytics/group/community', { headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` }, signal: controller.signal })
      .then(result => { if (active) setData(result) })
      .catch(err => { if (active) setError(err.status === 403 ? 'Insights está disponible para perfiles de autor y miembros de librerías o editoriales.' : 'No se pudieron consultar los indicadores. Puedes reintentar.') })
      .finally(() => { if (active) setBusy(false) })
    return () => { active = false; controller.abort() }
  }, [refresh, user?.id])
  return <section className="page-width page community-dashboard">
    <div className="community-heading"><div><span className="kicker">AUTORES · LIBRERÍAS · EDITORIALES</span><h1 className="page-title">LibrIA Insights</h1></div>
      <button className="button secondary" disabled={busy} onClick={() => setRefresh(value => value + 1)}>Actualizar indicadores</button></div>
    <p>Descubre la actividad y las tendencias de la comunidad a partir de los registros guardados en LibrIA. La popularidad no describe los gustos de un lector particular.</p>
    <ActionStatus busy={busy} error={error} message={busy ? 'Preparando indicadores de la comunidad…' : data ? 'Consulta completada.' : ''} />
    {data?.period && <p>Período: {formatDate(data.period.start)} — {formatDate(data.period.cutoff)}. Comparación con los 30 días anteriores. Publicación diaria con protección de privacidad.</p>}
    {data?.status === 'insufficient_group' && <p className="notice">Aún no hay suficientes participantes para publicar estadísticas. Se necesitan al menos {data.minimum_participants}; no se muestran datos de ejemplo.</p>}
    {data?.status === 'ready' && <div className="community-grid">{data.indicators.map(indicator => <article className="community-card" key={indicator.id}>
      <span className="kicker">{indicator.id}</span><h2>{indicator.label}</h2><p className="community-unit">{indicator.unit}</p>
      {indicator.items.length ? <ul>{indicator.items.map((item, index) => <li key={item.work_id || item.profile_id || `${item.title}-${index}`}>
        <div><span>{item.title}</span><strong>{item.value}{indicator.unit === 'porcentaje' ? '%' : ''}</strong></div>
        {indicator.unit === 'porcentaje' && <progress max="100" value={item.value} aria-label={item.title} />}
        {item.current !== undefined && <small>Actual: {item.current} · Anterior: {item.previous}</small>}
        {item.contributors !== undefined && <small>{item.contributors} valoraciones, aproximadamente</small>}
      </li>)}</ul> : <p>No hay datos suficientes que cumplan los requisitos de publicación.</p>}
      <details><summary>Cómo se calcula</summary><p>{indicator.definition}</p><p>Se requieren al menos {data.minimum_contributors} contribuyentes por resultado. Los conteos se redondean y las contribuciones se limitan.</p></details>
    </article>)}</div>}
    {data?.limitations && <details className="community-limits"><summary>Alcance y privacidad</summary><ul>{data.limitations.map(item => <li key={item}>{item}</li>)}</ul></details>}
  </section>
}
