import { useEffect, useState } from 'react'
import { BrainCircuit, RefreshCw, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiRequest } from '../api/client'
import './AnalysisPanel.css'

const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })
const formatDate = value => new Intl.DateTimeFormat('es-CL', { timeZone: 'America/Santiago', dateStyle: 'medium' }).format(new Date(value))
const provenanceLabels = { simulated: 'Escenario ficticio', unclassified: 'Origen sin acreditar', operational: 'Origen real acreditado' }
const errorMessage = (status, group) => ({
  403: group ? 'Esta sección requiere un perfil de autor o pertenecer a una editorial o librería.' : 'Necesitas al menos 10 libros registrados. Actualiza los datos para comprobar tu disponibilidad.',
  409: 'Ya se está generando esta interpretación. Espera y actualiza la pantalla.',
  422: 'Todavía no hay datos suficientes para esta interpretación.',
  429: 'Espera un minuto antes de generar otra interpretación.',
  503: 'El modelo local no está disponible. Inicia Ollama en el servidor y vuelve a actualizar.',
}[status] || 'No se pudo obtener la interpretación. Puedes volver a intentarlo.')

export default function AnalysisPanel({ group = false }) {
  const [data, setData] = useState(null)
  const [provenance, setProvenance] = useState('simulated')
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const base = group ? '/analytics/group' : '/analytics/me'
  useEffect(() => {
    let active = true
    setLoading(true)
    setData(null)
    setError('')
    apiRequest(`${base}/insights?provenance=${provenance}`, { headers: headers() }).then(result => {
      if (active) setData(result)
    }).catch(err => { if (active) setError(errorMessage(err.status, group)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [base, group, provenance, refresh])

  async function generate() {
    setGenerating(true)
    setError('')
    try {
      const result = await apiRequest(`${base}/interpretation`, {
        method: 'POST', headers: headers(), body: JSON.stringify({ provenance }),
      })
      setData(current => ({ ...current, interpretation: result }))
    } catch (err) { setError(errorMessage(err.status, group)) }
    finally { setGenerating(false) }
  }

  const evidence = data?.evidence
  const interpretation = data?.interpretation
  const content = interpretation?.content
  if (!group && data?.status === 'locked') return <section className="page-width page insights-page"><h1 className="page-title">Tu ADN lector</h1><p className="notice">Necesitas registrar al menos {data.minimum_books} libros en tu biblioteca. Tienes {data.book_count}; te faltan {data.missing_books}.</p><p>Cuentan libros distintos en cualquier estado. Una relectura no cuenta como otro libro.</p><Link className="button primary" to="/books">Explorar y agregar libros</Link> <button className="button" disabled={loading} onClick={() => setRefresh(value => value + 1)}>Actualizar disponibilidad</button></section>
  return <section className="page-width page insights-page">
    <span className="kicker">{group ? 'AUTORES · EDITORIALES · LIBRERÍAS' : 'MIS ANÁLISIS'}</span>
    <h1 className="page-title">{group ? 'Pulso de la comunidad' : 'Tu ADN lector'}</h1>
    <p className="page-lead">{group ? 'Una interpretación de la actividad agregada para orientar iniciativas de lectura.' : 'Una interpretación de tus registros de lectura, basada en los datos preparados por el ETL.'}</p>
    <div className="insights-toolbar"><label>Datos que deseas consultar<select value={provenance} disabled={generating} onChange={event => setProvenance(event.target.value)}>
      {Object.entries(provenanceLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
    </select></label><button className="button secondary" disabled={loading || generating} onClick={() => setRefresh(value => value + 1)}><RefreshCw size={17} /> Actualizar datos</button></div>
    {error && <p className="notice" role="alert">{error}</p>}
    {loading && <p role="status">Consultando indicadores…</p>}
    {data && !evidence && <article className="analysis-card"><BrainCircuit /><h2>{group ? 'Todavía no podemos publicar este conjunto' : 'Todavía no hay registros analíticos propios'}</h2>
      <p>{group ? `El resumen requiere al menos ${data.minimum_participants} participantes de la misma procedencia. Los grupos pequeños no se muestran.` : 'Prueba otra procedencia o registra actividad y espera una nueva carga del ETL.'}</p></article>}
    {evidence && <>
      <p className="insights-source"><strong>{provenanceLabels[provenance]}</strong> · Desde {formatDate(evidence.period.start)} hasta {formatDate(evidence.period.cutoff)} · {evidence.period.source === 'manual' ? 'Carga manual' : 'Cierres diarios'}
        {group && <> · Resumen publicado el {evidence.release_date}</>}</p>
      {provenance === 'simulated' && <p className="notice">Estos resultados describen datos ficticios de demostración.</p>}
      {provenance === 'unclassified' && <p className="notice">La procedencia de estos registros no acredita que sean datos reales.</p>}
      <div className="insights-metrics">{Object.entries(evidence.metrics).map(([code, item]) => <article key={code}><span>{item.label}</span><strong>{new Intl.NumberFormat('es-CL', { maximumFractionDigits: 2 }).format(item.value)}</strong><small>{item.unit}</small></article>)}</div>
      {!group && evidence.qualitative?.length > 0 && <details className="insights-limits"><summary>Reflexiones privadas utilizadas en tu ADN lector</summary><p>Emociones y apreciaciones que declaraste al finalizar libros, preparadas por el ETL.</p>{evidence.qualitative.map((item, index) => <article key={index}><p><strong>Emociones:</strong> {item.emotions.join(' · ') || 'Sin indicar'}</p><p><strong>Aspectos:</strong> {item.aspects.join(' · ') || 'Sin indicar'} · <strong>Experiencia:</strong> {item.sentiment || 'Sin indicar'}</p>{item.reflection && <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{item.reflection}</p>}</article>)}</details>}
      <article className="analysis-card insights-interpretation"><div className="insights-title"><h2><Sparkles size={22} /> Interpretación con IA local</h2><button className="button primary" disabled={generating || !data.ai_ready} onClick={generate}>{generating ? 'Interpretando…' : content ? 'Consultar interpretación' : 'Generar interpretación'}</button></div>
        {!data.ai_ready && <p className="notice">El modelo local todavía no está disponible en el servidor.</p>}
        {generating && <p role="status">Ollama está interpretando los indicadores. La primera ejecución puede tardar mientras carga el modelo.</p>}
        {!content && !generating && <p>Genera una interpretación de {group ? 'este resumen agregado' : 'tus indicadores'}. Los datos se procesan en este equipo.</p>}
        {content && <><h3>{content.title}</h3><p>{content.summary}</p>
          <ul className="insights-observations">{content.observations.map((item, index) => <li key={index}><strong>{evidence.metrics[item.metric]?.label}: {evidence.metrics[item.metric]?.value}</strong><p>{item.interpretation}</p></li>)}</ul>
          {content.suggestions.length > 0 && <><h3>{group ? 'Iniciativas que puedes explorar' : 'Sugerencias para tus próximas lecturas'}</h3><ul>{content.suggestions.map((item, index) => <li key={index}>{item}</li>)}</ul></>}
          <small>Generada el {formatDate(interpretation.created_at)} con Ollama · {interpretation.model}. La IA puede equivocarse; las cifras mostradas provienen del ETL.</small>
        </>}
      </article>
      <details className="insights-limits"><summary>Alcance de esta interpretación</summary><ul>{[...new Set([...evidence.limitations, ...(content?.limitations || [])])].map((item, index) => <li key={index}>{item}</li>)}</ul>
        {!group && evidence.period.source === 'daily' && <p>Hay {evidence.period.daily_closures} cierres disponibles en el intervalo. La cobertura puede ser incompleta.</p>}
        {group && <p>El resumen se mantiene fijo durante el día y no permite consultar personas ni filtrar grupos pequeños.</p>}
      </details>
    </>}
  </section>
}
