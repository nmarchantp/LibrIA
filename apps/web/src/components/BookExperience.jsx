import { bookAnalysisMessages } from './bookAnalysisState'
import { BookOpenText, CircleAlert, CircleHelp, Heart, Quote, RefreshCw, Sparkles, ThumbsUp } from 'lucide-react'
import { useLibrary } from '../context/LibraryContext'
import BookCover from './BookCover'
import { formatAnalysisDate, sourceLabels } from './adaptiveAnalysisLabels'
import './ReaderDna.css'
import './BookExperience.css'

// Each AI finding group becomes a card category; only data returned by the API is shown.
const groups = [
  ['emotions', 'Emoción expresada', Heart],
  ['valued_aspects', 'Aspecto valorado', ThumbsUp],
  ['questioned_aspects', 'Aspecto cuestionado', CircleHelp],
  ['preferences', 'Preferencia identificada', Sparkles],
]
const certainty = { consolidado: 'Experiencia consolidada', provisional: 'Primeras impresiones', insuficiente: 'Evidencia insuficiente' }
const sentiments = { positivo: 'Positivo', negativo: 'Negativo', mixto: 'Mixto' }
const abandonment = { externo: 'Motivos externos a la obra', obra: 'Opinión sobre la obra', mixto: 'Motivos mixtos' }
// Messages shown while a durable provider job is processing.
const sourcesOf = claim => [...new Set(claim.evidence_ids.map(id => sourceLabels[id.split(':')[0]] || 'Registro propio'))].join(' · ')

function WaitingFindings({ processing }) {
  const text = processing ? 'Análisis en curso. El resultado aparecerá automáticamente cuando esté listo.' : 'Tu solicitud está pendiente. Puedes consultar arriba cuándo podrá comenzar.'
  return <div className="bx-waiting" role="status" aria-live="polite">
    <BookOpenText className="bx-waiting-icon" size={26} aria-hidden="true" />
    <p key={text}>{text}</p>
  </div>
}

function WorkHeading({ book, children }) {
  return <header className="bx-work">
    {book && <BookCover book={book} />}
    <div className="bx-work-copy">
      <span className="dna-kicker">Obra analizada</span>
      <h3>{book?.title || 'Esta obra'}</h3>
      {book?.author && <small>{book.author}</small>}
    </div>
    {children}
  </header>
}

function FindingCard({ claim, label, icon: Icon }) {
  return <article className="bx-finding">
    <header><span className="bx-chip">{label}</span><Icon size={17} aria-hidden="true" /></header>
    <p>{claim.text}</p>
    <footer>Fuente: {sourcesOf(claim)}</footer>
  </article>
}

function NightlyStatus({ data, onWriteReview, onRetry, submitting }) {
  if (data?.retry_scheduled) {
    return <aside className="dna-notice" role="status"><strong>La lechuza prepara otro intento</strong>
      <p>La generación anterior falló. Tu reintento está guardado y se habilitará con la próxima actualización de datos, automática o iniciada por un administrador.</p>
      {data.analysis && <small>Actualización pendiente · Tu interpretación anterior sigue disponible.</small>}
    </aside>
  }
  if (data?.generation_enabled === false && data?.job?.status === 'pending' && data?.status !== 'completed') {
    return <aside className="dna-notice" role="status"><strong>Tu lechuza espera la señal de partida</strong>
      <p>Tu solicitud está guardada, pero la generación está desactivada. Un administrador debe habilitar el servicio para continuar.</p>
      {data.analysis && <small>Actualización pendiente · Tu interpretación anterior sigue disponible.</small>}
    </aside>
  }
  const [title, message] = bookAnalysisMessages[data?.status] || []
  if (!title || data.status === 'completed') return null
  return <aside className="dna-notice" role="status" aria-live="polite">
    <strong>{title}</strong><p>{message}</p>
    {data.needs_refresh && data.analysis && <small>Actualización pendiente · Interpretación de una versión anterior</small>}
    {data.status === 'requires_review' && <a href="#book-review-form" onClick={onWriteReview}>Escribir reseña</a>}
    {data.status === 'failed' && data.retry_exhausted && <p>Se alcanzó el límite de intentos. Contacta con soporte para revisar el problema.</p>}
    {data.status === 'failed' && !data.retry_exhausted && <button className="button secondary" type="button" disabled={submitting} onClick={onRetry}>Programar reintento</button>}
  </aside>
}

export default function BookExperience({ workId, data, analysis, working, error, notice, onRefresh, refreshDisabled, refreshLabel, submitting, information, setInformation, onFeedback, onWriteReview, onRetry, history, historyBusy, onLoadHistory }) {
  const { getBook } = useLibrary()
  const book = getBook(workId)
  const content = analysis?.content
  const observationSources = (field, index = 0) => {
    const ids = content?.observation_evidence?.find(item => item.field === field && item.index === index)?.evidence_ids || []
    const labels = [...new Set(ids.map(id => sourceLabels[id.split(':')[0]] || 'Registro propio'))]
    return labels.length > 0 ? <small>Fuente: {labels.join(' · ')}</small> : null
  }
  const historyView = analysis && <details className="bx-evidence"><summary onClick={() => { if (!history) onLoadHistory() }}>Versiones anteriores</summary>
    {historyBusy && <p role="status">Consultando mensajes anteriores…</p>}
    {history?.map(item => <article key={item.id}><small>{formatAnalysisDate(item.created_at)}</small><p>{item.content.experience_summary}</p></article>)}
  </details>
  if (content?.experience_summary) return <section className="book-experience-view" aria-label="Análisis personal persistido">
    <header className="dna-header"><div><span className="dna-kicker">Solo esta lectura</span><h2>Tu experiencia con este libro</h2><p>Análisis privado de tu valoración, reseña y notas al terminar o abandonar esta lectura.</p></div>
      <button type="button" className="dna-refresh" disabled={refreshDisabled} onClick={onRefresh}><RefreshCw size={15} aria-hidden="true" />{refreshLabel}</button></header>
    <NightlyStatus data={data} onWriteReview={onWriteReview} onRetry={onRetry} submitting={submitting} />
    {error && <p role="alert">{error}</p>}
    {historyView}
    {notice && <p className="dna-notice" role="status">{notice}</p>}
    <article className="dna-card bx-result"><WorkHeading book={book} /><blockquote className="bx-quote"><Quote size={16} aria-hidden="true" /><p>{content.experience_summary}</p></blockquote>
      {observationSources('experience_summary')}
      {[['valued_elements','Elementos valorados'],['friction_points','Puntos de fricción'],['themes_and_interests','Temas e intereses'],['emotional_response','Respuestas expresadas'],['rating_observations','Observaciones de valoración']].map(([key,label]) => content[key]?.length > 0 && <section key={key}><h3>{label}</h3><ul>{content[key].map((item,index)=><li key={index}><p>{item}</p>{observationSources(key, index)}</li>)}</ul></section>)}
      <details className="bx-evidence"><summary>Evidencias y metadatos</summary><p>Evento: {content.event_kind === 'finish' ? 'finalización' : 'abandono'}</p><p>Modelo: {analysis.model}</p><p>{content.evidence_ids.length} referencia(s) validadas.</p></details>
    </article>
    <article className="dna-card bx-feedback"><form onSubmit={event => { event.preventDefault(); onFeedback('correct') }}><h3>¿Hay algo que corregir?</h3><textarea maxLength={3000} rows={4} disabled={submitting} value={information} onChange={event => setInformation(event.target.value)} /><div className="bx-feedback-actions"><button className="button primary" disabled={working || !information.trim()}>Guardar corrección</button><button className="button secondary" type="button" disabled={working} onClick={() => onFeedback('confirm')}>Me representa</button><button className="button secondary" type="button" disabled={working} onClick={() => onFeedback('reject')}>No me representa</button></div></form></article>
  </section>
  const findings = content ? groups.flatMap(([key, label, icon]) => (content[key] || []).map((claim, index) => ({ claim, label, icon, key: `${key}-${index}` }))) : []
  return <section className="book-experience-view" aria-label="Análisis personal de esta obra">
    <header className="dna-header">
      <div><span className="dna-kicker">Solo este libro</span><h2>Tu experiencia con este libro</h2><p>Interpretación privada de tu valoración y tus aportes sobre esta obra.</p></div>
      <button type="button" className="dna-refresh" disabled={refreshDisabled} onClick={onRefresh}><RefreshCw size={15} aria-hidden="true" />{refreshLabel}</button>
    </header>
    {data?.status === 'awaiting_terminal_event' && <p className="dna-notice">Primero marca esta lectura como terminada o abandonada. Completa tu valoración, reseña y notas, y luego pulsa «Solicitar análisis».</p>}
    {data?.status === 'obsolete' && <p className="dna-notice">Tu análisis anterior necesita actualizarse. Pulsa «Solicitar análisis» para preparar una nueva versión.</p>}
    {data?.status === 'budget_exhausted' && <p className="dna-notice">El presupuesto mensual está agotado. El evento permanece registrado sin crear solicitudes adicionales.</p>}
    <NightlyStatus data={data} onWriteReview={onWriteReview} onRetry={onRetry} submitting={submitting} />
    {error && <p role="alert">{error}</p>}
    {historyView}
    {notice && <p className="dna-notice" role="status">{notice}</p>}
    {working && analysis && <p className="dna-muted">Mientras se procesa la actualización, puedes consultar la última versión válida.</p>}
    {/* A newly rated book has no previous version yet, so the wait gets its own card. */}
    {working && data && !content && <article className="dna-card bx-result">
      <WorkHeading book={book} />
      <WaitingFindings processing={(data?.job?.status || data?.status) === 'processing'} />
    </article>}
    {content && <article className="dna-card bx-result">
      <WorkHeading book={book}>
        <dl className="bx-levels">
          <div className={`bx-level is-${content.analysis_state}`}><dt>Nivel de certeza</dt><dd><span className="bx-dot" aria-hidden="true" />{certainty[content.analysis_state] || 'Evidencia insuficiente'}</dd></div>
          {sentiments[content.sentiment] && <div className={`bx-level is-${content.sentiment}`}><dt>Valoración interpretada</dt><dd><span className="bx-dot" aria-hidden="true" />{sentiments[content.sentiment]}</dd></div>}
        </dl>
      </WorkHeading>
      <blockquote className="bx-quote"><Quote size={16} aria-hidden="true" /><p>{content.interpretation}</p></blockquote>
      {abandonment[content.abandonment_context] && <p className="bx-abandonment"><CircleAlert size={16} aria-hidden="true" /><span><strong>Contexto declarado del abandono:</strong> {abandonment[content.abandonment_context]}. No equivale por sí solo a rechazo.</span></p>}
      <div className="dna-subheading bx-findings-heading"><span className="dna-kicker"><Sparkles size={14} aria-hidden="true" />Hallazgos identificados</span>{findings.length > 0 && <small>{findings.length} {findings.length === 1 ? 'hallazgo destacado' : 'hallazgos destacados'}</small>}</div>
      {findings.length ? <ul className="bx-findings">{findings.map(item => <li key={item.key}><FindingCard claim={item.claim} label={item.label} icon={item.icon} /></li>)}</ul>
        : working ? <WaitingFindings /> : <p className="dna-empty">La IA no identificó hallazgos con suficiente respaldo en esta versión.</p>}
      <details className="bx-evidence">
        <summary><span>Evidencias y límites de esta versión</span><small>Ver motor y metadatos</small></summary>
        <div className="dna-details">
          <dl>
            <div><dt>Versión</dt><dd>{analysis.version}</dd></div>
            <div><dt>Generado</dt><dd>{formatAnalysisDate(analysis.created_at)}</dd></div>
            {analysis.source_cutoff_at && <div><dt>Datos al</dt><dd>{formatAnalysisDate(analysis.source_cutoff_at)}</dd></div>}
            <div><dt>Modelo</dt><dd>{analysis.model}</dd></div>
          </dl>
          <h4>Evidencias consideradas</h4>
          <ul>{data.evidence.map(item => <li key={item.source_key}>{sourceLabels[item.source_kind] || 'Registro propio'} · <code>{item.source_id}</code></li>)}</ul>
          <h4>Límites de esta versión</h4>
          <ul>{content.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>
          <p>Estas son interpretaciones de IA sobre registros de lectura. No describen tu personalidad ni tu salud mental.</p>
        </div>
      </details>
    </article>}
    {content && <article className="dna-card bx-feedback">
      <form onSubmit={event => { event.preventDefault(); onFeedback('correct') }}>
        <h3 id={`bx-correction-${workId}`}>¿Hay algo que corregir?</h3>
        <textarea aria-labelledby={`bx-correction-${workId}`} maxLength={3000} rows={4} disabled={submitting} value={information} onChange={event => setInformation(event.target.value)} placeholder="Explica qué interpretó mal la IA o confirma qué preferencias sí te representan." />
        <div className="bx-feedback-actions">
          <button className="button primary" disabled={working || !information.trim()}>Guardar corrección</button>
          <button className="button secondary" type="button" disabled={working} onClick={() => onFeedback('confirm')}>Me representa</button>
          <button className="button secondary" type="button" disabled={working} onClick={() => onFeedback('reject')}>No me representa</button>
        </div>
      </form>
    </article>}
  </section>
}
