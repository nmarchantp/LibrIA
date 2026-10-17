import { useEffect, useState } from 'react'
import { apiRequest } from '../api/client'
import ActionStatus from './ActionStatus'
import { useAuth } from '../context/AuthContext'
import './AdaptiveAnalysis.css'

const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })
const date = value => new Intl.DateTimeFormat('es-CL', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Santiago' }).format(new Date(value))
const labels = {
  emotions: 'Emociones expresadas', valued_aspects: 'Aspectos valorados', questioned_aspects: 'Aspectos cuestionados', preferences: 'Preferencias identificadas',
  historical_affinities: 'Preferencias que se repiten', recent_affinities: 'Lo que estás valorando últimamente', exploratory_interests: 'Lo que estás explorando',
  satisfaction_factors: 'Lo que más disfrutas', abandonment_factors: 'Lo que dificulta continuar una lectura', confirmed_preferences: 'Lo que tú confirmaste o corregiste',
}
const sourceLabels = { reading: 'Lectura y cuaderno', review: 'Reseña y valoración propia', reflection: 'Reflexión de cierre', note: 'Nota propia', theory: 'Teoría propia', analysis: 'Experiencia individual', feedback: 'Tu corrección o confirmación' }
const errors = { context_capacity: 'Tu biblioteca supera la capacidad actual de contexto. No se ha publicado un análisis parcial como si fuera completo.', source_removed: 'La fuente ya no está disponible.', book_analysis_failed: 'Una experiencia individual no pudo analizarse. Reintenta desde la ficha de ese libro.', provider_timeout: 'Ollama superó el tiempo de espera. Puedes reintentar.' }

function PrivateAnalysis({ workId, scope }) {
  const isBook = scope === 'book'
  const base = isBook ? `/me/ai/books/${workId}` : '/me/ai/profile'
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [information, setInformation] = useState('')
  const [history, setHistory] = useState(null)
  const [historyBusy, setHistoryBusy] = useState(false)
  const [expiredDeadline, setExpiredDeadline] = useState(null)
  const deadline = data?.job?.deadline_at
  useEffect(() => {
    if(isBook || !deadline || !['pending','processing'].includes(data?.job?.status)) return
    const timer=setTimeout(() => setExpiredDeadline(deadline),Math.max(0,new Date(deadline).getTime()-Date.now()))
    return () => clearTimeout(timer)
  },[deadline,isBook,data?.job?.status])
  useEffect(() => {
    let active = true
    let timer
    async function load() {
      try {
        let result = await apiRequest(base, { headers: headers(), signal:AbortSignal.timeout(5000) })
        if (!active) return
        if (result.status !== 'awaiting_rating' && ((!result.job && !result.analysis) || result.needs_refresh)) {
          await apiRequest(`${base}/refresh`, { method: 'POST', headers: headers(), signal:AbortSignal.timeout(5000) })
          if (!active) return
          result = await apiRequest(base, { headers: headers(), signal:AbortSignal.timeout(5000) })
          if (!active) return
        }
        setData(result)
        setError('')
        setLoading(false)
        // Keep detecting updates made elsewhere, without submitting new jobs.
        timer = setTimeout(load, ['pending', 'processing'].includes(result.job?.status) ? 2500 : 15000)
      } catch {
        if (active) { setLoading(false); setError('No se pudo consultar tu análisis privado. Reintenta.'); timer = setTimeout(load, 15000) }
      }
    }
    load()
    return () => { active = false; clearTimeout(timer) }
  }, [base, refresh])

  async function requestRefresh() {
    setSubmitting(true); setError(''); setNotice('')
    try {
      const result = await apiRequest(`${base}/refresh`, { method: 'POST', headers: headers(), signal:AbortSignal.timeout(5000) })
      setData(current => ({ ...current, job: result.job || { status: result.status || 'pending' } }))
      setRefresh(value => value + 1)
    } catch (err) {
      if (['TimeoutError','AbortError'].includes(err.name)) {
        setNotice('La confirmación de la solicitud está tardando. Consultando si el análisis ya está en curso…')
        setRefresh(value => value + 1)
      } else setError('No se pudo solicitar el análisis. Puedes reintentar.')
    }
    finally { setSubmitting(false) }
  }

  async function sendFeedback(action) {
    setSubmitting(true); setError(''); setNotice('')
    try {
      await apiRequest('/me/ai/feedback', { method: 'POST', headers: headers(), body: JSON.stringify({ analysis_id: data.analysis.id, action, information }) })
      setInformation(''); setHistory(null)
      setData(current => ({ ...current, analysis: action === 'confirm' ? current.analysis : null, job: { status: 'pending' } }))
      setNotice('Tu respuesta quedó registrada y tendrá prioridad en la próxima interpretación.')
      setRefresh(value => value + 1)
    } catch { setError('No se pudo guardar tu respuesta. Actualiza el análisis antes de reintentar.') }
    finally { setSubmitting(false) }
  }

  async function loadHistory(before) {
    setHistoryBusy(true); setError('')
    try {
      const result = await apiRequest(`/me/ai/profile/history${before ? `?before=${before}` : ''}`, { headers: headers() })
      setHistory(current => before ? [...current, ...result.items] : result.items)
    } catch { setError('No se pudo consultar el historial privado.') }
    finally { setHistoryBusy(false) }
  }

  const analysis = data?.scope === scope ? data.analysis : null
  const summary = data?.library_summary
  const displayLabels = Object.entries(labels).filter(([key]) => isBook ? ['emotions','valued_aspects','questioned_aspects','preferences'].includes(key) : !['emotions','valued_aspects','questioned_aspects','preferences'].includes(key))
  const supportCount = claim => new Set((data?.evidence || []).filter(source => claim.evidence_ids.includes(source.source_key)).map(source => source.work_id).filter(Boolean)).size
  const supportingBooks = claim => [...new Set((data?.evidence || []).filter(source => claim.evidence_ids.includes(source.source_key) && source.book_title).map(source => source.book_title))]
  const content = analysis?.content
  const expired = !isBook && ['pending','processing'].includes(data?.job?.status) && Boolean(deadline) && expiredDeadline === deadline
  const working = submitting || (!expired && (loading || ['pending', 'processing'].includes(data?.job?.status)))
  const failed = expired || data?.job?.status === 'failed'
  const message = submitting ? 'Registrando solicitud…' : loading ? 'Consultando tu análisis privado…' : data?.job?.status === 'pending' ? 'Análisis pendiente. Se procesará automáticamente.' : data?.job?.status === 'processing' ? 'Ollama está interpretando tus experiencias de lectura…' : analysis ? 'Análisis completado. Tu versión está disponible.' : ''
  return <section className={`adaptive-analysis ${isBook ? 'book-experience' : 'reader-dna'}`} aria-label={isBook ? 'Análisis personal de esta obra' : 'ADN lector global'}>
    <div className="adaptive-heading"><div><span className="kicker">{isBook ? 'SOLO ESTE LIBRO' : 'ADN LECTOR · BIBLIOTECA PERSONAL'}</span><h2>{isBook ? 'Tu experiencia con este libro' : 'Tu universo literario'}</h2></div>
      <button className="button secondary" disabled={working} onClick={requestRefresh}>{working ? 'Procesando…' : failed ? 'Reintentar análisis' : 'Actualizar análisis'}</button></div>
    <p>{isBook ? 'Interpretación privada de tu valoración y tus aportes sobre esta obra.' : 'Tu perfil literario se construye al contrastar los libros de tu biblioteca, tus valoraciones y tus correcciones.'}</p>
    {!isBook && summary && <><div className="reader-dna-stats">{[['finished','Terminados'],['reading','Leyendo'],['abandoned','Abandonados']].map(([key,label]) => <div key={key}><strong>{summary[key]}</strong><span>{label}</span></div>)}</div><p className="reader-dna-coverage">{summary.total} libros en tu biblioteca · {summary.rated} valorados · {summary.pending} por leer</p></>}
    {isBook && data?.status === 'awaiting_rating' && <p className="notice">Valora este libro para ver su análisis individual aquí.</p>}
    <ActionStatus busy={working} message={message} error={error || (expired || data?.job?.error_code === 'deadline_exceeded' ? 'No se pudo completar el ADN dentro de un minuto. Se conserva la última versión válida; puedes reintentar.' : failed ? errors[data.job.error_code] || 'El análisis no pudo completarse. Puedes reintentar; se conserva la última versión válida.' : '')} />
    {notice && <p role="status">{notice}</p>}
    {working && analysis && <p>Mientras se procesa la actualización, puedes consultar la última versión válida.</p>}
    {content && <article className="adaptive-result">
      <small>Versión {analysis.version} · {date(analysis.created_at)} · {analysis.model}</small>
      {analysis.source_cutoff_at && <small>Datos preparados al {date(analysis.source_cutoff_at)}</small>}
      {isBook && <p><strong>{content.analysis_state === 'consolidado' ? 'Experiencia consolidada' : content.analysis_state === 'provisional' ? 'Interpretación provisional' : 'Evidencia insuficiente'}</strong> · Valoración interpretada: {content.sentiment}</p>}
      {isBook && content.abandonment_context && content.abandonment_context !== 'indeterminado' && <p>Contexto declarado del abandono: {content.abandonment_context === 'externo' ? 'Motivos externos a la obra' : content.abandonment_context === 'obra' ? 'Opinión sobre la obra' : 'Motivos mixtos'}. No equivale por sí solo a rechazo.</p>}
      {isBook ? <p>{content.interpretation}</p> : <div className="reader-dna-identity"><h3>Tu identidad literaria</h3><p>{content.literary_identity}</p><small>Lecturas que respaldan esta identidad: {supportingBooks({ evidence_ids: content.identity_evidence_ids || [] }).join(' · ') || 'Aún se necesitan más experiencias valoradas.'}</small></div>}
      {!isBook && <><h3>Afinidades detectadas</h3><p className="reader-dna-coverage">Lo que disfrutas de los temas, personajes, mundos y estilos de tus lecturas, según tus valoraciones y aportes. Cada afinidad indica los libros que la respaldan.</p></>}
      {!isBook && !displayLabels.some(([key]) => content[key]?.length) && <p>Aún no hay afinidades suficientemente respaldadas para mostrarlas.</p>}
      {displayLabels.map(([key, label]) => content[key]?.length > 0 && <div key={key}><h3>{label}</h3><ul>{content[key].map((claim, index) => <li key={index}>{claim.text}<small>{isBook ? `Fuentes: ${claim.evidence_ids.map(id => sourceLabels[id.split(':')[0]] || 'Registro propio').join(' · ')}` : supportingBooks(claim).length ? `Se observa en: ${supportingBooks(claim).join(' · ')}` : 'Basado en lo que tú confirmaste o corregiste'}</small>{!isBook && supportCount(claim)===1 && <small>Señal de una sola obra; todavía no confirma una preferencia que se repita.</small>}</li>)}</ul></div>)}
      {!isBook && <div className="reader-dna-global"><h3>Interpretación global</h3><p>{content.interpretation}</p></div>}
      <details><summary>Evidencias y límites de esta versión</summary><ul>{data.evidence.map(item => <li key={item.source_key}>{sourceLabels[item.source_kind] || 'Registro propio'} · <code>{item.source_id}</code></li>)}</ul><ul>{content.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul><p>Estas son interpretaciones de IA sobre registros de lectura. No describen tu personalidad ni tu salud mental.</p></details>
      <form className="adaptive-feedback" onSubmit={event => { event.preventDefault(); sendFeedback('correct') }}>
        <label>¿Hay algo que corregir?<textarea maxLength={3000} rows={3} disabled={submitting} value={information} onChange={event => setInformation(event.target.value)} placeholder="Explica qué interpretó mal la IA o confirma qué preferencias sí te representan." /></label>
        <div><button className="button primary" disabled={working || !information.trim()}>Guardar corrección</button>
          <button className="button secondary" type="button" disabled={working} onClick={() => sendFeedback('confirm')}>Me representa</button>
          <button className="button secondary" type="button" disabled={working} onClick={() => sendFeedback('reject')}>No me representa</button></div>
      </form>
    </article>}
    {!isBook && <div className="adaptive-history"><button className="button secondary" disabled={historyBusy || working} onClick={() => loadHistory()}>{historyBusy ? 'Consultando versiones…' : 'Consultar historial de versiones'}</button>
      {history && <><ul>{history.map(item => <li key={item.id}><strong>Versión {item.version}</strong> · {date(item.created_at)}<p>{item.valid && item.content.literary_identity ? item.content.interpretation : 'Versión anterior no vigente del perfil global.'}</p></li>)}</ul>{history.length > 0 && <button className="button" disabled={historyBusy} onClick={() => loadHistory(history.at(-1).version)}>Ver versiones anteriores</button>}</>}
    </div>}
  </section>
}

export default function AdaptiveAnalysis({ workId, scope = 'profile' }) {
  const { user } = useAuth()
  if (scope==='book' && !workId) return null
  return <PrivateAnalysis key={`${user?.id}:${scope}:${workId || 'profile'}`} scope={scope} workId={workId} />
}
