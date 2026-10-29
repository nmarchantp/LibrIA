import { useEffect, useState } from 'react'
import { BrainCircuit, RefreshCw, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiRequest } from '../api/client'
import './AnalysisPanel.css'
import ActionStatus from './ActionStatus'

const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })
const formatDate = value => new Intl.DateTimeFormat('es-CL', { timeZone: 'America/Santiago', dateStyle: 'medium' }).format(new Date(value))
const provenanceLabels = { unclassified: 'Origen sin acreditar', operational: 'Origen real acreditado' }
const errorMessage = (status, group) => ({
  403: group ? 'Esta sección requiere un perfil de autor o pertenecer a una editorial o librería.' : 'Necesitas al menos 10 libros registrados. Actualiza los datos para comprobar tu disponibilidad.',
  409: 'Ya se está generando esta interpretación. Espera y actualiza la pantalla.',
  422: 'Todavía no hay datos suficientes para esta interpretación.',
  429: 'Espera un minuto antes de generar otra interpretación.',
  502: 'La IA no pudo completar una interpretación válida de tus aportes. Vuelve a intentarlo.',
  501: 'Esta interpretación clásica aún no tiene un contrato Gemini aprobado.',
}[status] || 'No se pudo obtener la interpretación. Puedes volver a intentarlo.')

export default function AnalysisPanel({ group = false }) {
  const [data, setData] = useState(null)
  const [provenance, setProvenance] = useState('unclassified')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [completed, setCompleted] = useState('')
  const [refresh, setRefresh] = useState(0)
  const base = group ? '/analytics/group' : '/analytics/me'
  useEffect(() => {
    let active = true
    setLoading(true)
    setCompleted('')
    setData(null)
    setError('')
    apiRequest(`${base}/insights?provenance=${provenance}`, { headers: headers() }).then(result => {
      if (active) { setData(result); setCompleted('Consulta completada. Datos actualizados al último corte disponible.') }
    }).catch(err => { if (active) setError(errorMessage(err.status, group)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [base, group, provenance, refresh])

  const evidence = data?.evidence
  const interpretation = data?.interpretation
  const content = interpretation?.content
  if (!group && data?.status === 'locked') return <section className="page-width page insights-page"><h1 className="page-title">Tu ADN lector</h1><p className="notice">Necesitas registrar al menos {data.minimum_books} libros en tu biblioteca. Tienes {data.book_count}; te faltan {data.missing_books}.</p><p>Cuentan libros distintos en cualquier estado. Una relectura no cuenta como otro libro.</p><Link className="button primary" to="/books">Explorar y agregar libros</Link> <button className="button" disabled={loading} onClick={() => setRefresh(value => value + 1)}>Actualizar disponibilidad</button></section>
  return <section className="page-width page insights-page">
    <span className="kicker">{group ? 'AUTORES · EDITORIALES · LIBRERÍAS' : 'MIS ANÁLISIS'}</span>
    <h1 className="page-title">{group ? 'Pulso de la comunidad' : 'Tu ADN lector'}</h1>
    <p className="page-lead">{group ? 'Una interpretación de la actividad agregada para orientar iniciativas de lectura.' : 'Una interpretación de tus registros de lectura, basada en los datos preparados por el ETL.'}</p>
    <div className="insights-toolbar"><label>Datos que deseas consultar<select value={provenance} disabled={loading} onChange={event => setProvenance(event.target.value)}>
      {Object.entries(provenanceLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
    </select></label><button className="button secondary" disabled={loading} onClick={() => setRefresh(value => value + 1)}><RefreshCw size={17} /> Actualizar datos</button></div>
    <ActionStatus busy={loading} message={loading ? 'Consultando datos y resultados persistidos…' : error ? '' : completed} error={error} floating />
    {data && !evidence && <article className="analysis-card"><BrainCircuit /><h2>{group ? 'Todavía no podemos publicar este conjunto' : 'Todavía no hay registros analíticos propios'}</h2>
      <p>{group ? `El resumen requiere al menos ${data.minimum_participants} participantes de la misma procedencia. Los grupos pequeños no se muestran.` : 'Registra actividad y espera una nueva carga del ETL. No se generan datos de ejemplo.'}</p></article>}
    {evidence && <>
      <p className="insights-source"><strong>{provenanceLabels[provenance]}</strong> · Desde {formatDate(evidence.period.start)} hasta {formatDate(evidence.period.cutoff)} · {evidence.period.source === 'manual' ? 'Carga manual' : 'Cierres diarios'}
        {group && <> · Resumen publicado el {evidence.release_date}</>}</p>
      {provenance === 'unclassified' && <p className="notice">La procedencia de estos registros no acredita que sean datos reales.</p>}
      <div className="insights-metrics">{Object.entries(evidence.metrics).map(([code, item]) => <article key={code}><span>{item.label}</span><strong>{new Intl.NumberFormat('es-CL', { maximumFractionDigits: 2 }).format(item.value)}</strong><small>{item.unit}</small></article>)}</div>
      {!group && evidence.qualitative?.length > 0 && <details className="insights-limits"><summary>Reflexiones privadas utilizadas en tu ADN lector</summary><p>Emociones y apreciaciones que declaraste al finalizar libros, preparadas por el ETL.</p>{evidence.qualitative.map((item, index) => <article key={index}><p><strong>Emociones:</strong> {item.emotions.join(' · ') || 'Sin indicar'}</p><p><strong>Aspectos:</strong> {item.aspects.join(' · ') || 'Sin indicar'} · <strong>Experiencia:</strong> {item.sentiment || 'Sin indicar'}</p>{item.reflection && <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{item.reflection}</p>}</article>)}</details>}
      {!group && evidence.reader_contributions?.length > 0 && <details className="insights-limits"><summary>Aportes propios utilizados en tu perfil lector</summary>
        <p>Instant?nea acumulada al corte del ETL: rese?as privadas y p?blicas, valoraciones, notas, teor?as y cuaderno. Solo se utiliza en tu an?lisis personal.</p>
        {evidence.contributions_truncated && <p className="notice">La muestra est? limitada o contiene textos recortados para el an?lisis con IA.</p>}
        {evidence.reader_contributions.map(item => <article key={`${item.kind}:${item.source_id}`}>
          <h3>{item.title}</h3><small>{{ notebook: 'Cuaderno', review: 'Rese?a y valoraci?n', note: 'Nota', theory: 'Teor?a' }[item.kind]} ? {formatDate(item.recorded_at)}</small>
          {item.rating != null && <p>Valoraci?n general: {item.rating}/5</p>}
          {Object.keys(item.dimension_ratings || {}).length > 0 && <p>Valoraciones por aspecto: {Object.entries(item.dimension_ratings).map(([key, value]) => `${key}: ${value}/5`).join(' ? ')}</p>}
          {item.body && <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{item.body}</p>}
          {Object.entries(item.notebook || {}).map(([key, value]) => value && <p key={key} style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}><strong>{{ characters: 'Personajes', places: 'Sitios', summary: 'Resumen' }[key]}: </strong>{value}</p>)}
        </article>)}
      </details>}
      <article className="analysis-card insights-interpretation"><div className="insights-title"><h2><Sparkles size={22} /> Interpretación persistida</h2></div>
        {!content && <p className="notice">La interpretación {group ? 'grupal' : 'clásica personal'} todavía no tiene equivalente Gemini aprobado. Los indicadores ETL siguen disponibles y no se envían al proveedor.</p>}
        {content && <><h3>{content.title}</h3><p>{content.summary}</p>
          <ul className="insights-observations">{content.observations.map((item, index) => <li key={index}><strong>{evidence.metrics[item.metric]?.label}: {evidence.metrics[item.metric]?.value}</strong><p>{item.interpretation}</p></li>)}</ul>
          {content.suggestions.length > 0 && <><h3>{group ? 'Iniciativas que puedes explorar' : 'Sugerencias para tus próximas lecturas'}</h3><ul>{content.suggestions.map((item, index) => <li key={index}>{item}</li>)}</ul></>}
          <small>Resultado histórico generado el {formatDate(interpretation.created_at)} · {interpretation.provider} · {interpretation.model}. No se regenera desde esta pantalla.</small>
        </>}
      </article>
      <details className="insights-limits"><summary>Alcance de esta interpretación</summary><ul>{[...new Set([...evidence.limitations, ...(content?.limitations || [])])].map((item, index) => <li key={index}>{item}</li>)}</ul>
        {!group && evidence.period.source === 'daily' && <p>Hay {evidence.period.daily_closures} cierres disponibles en el intervalo. La cobertura puede ser incompleta.</p>}
        {group && <p>El resumen se mantiene fijo durante el día y no permite consultar personas ni filtrar grupos pequeños.</p>}
      </details>
    </>}
  </section>
}
