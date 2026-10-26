import { useEffect, useState } from 'react'
import { BookOpenText, CheckCircle2, CircleAlert, CircleHelp, Heart, LoaderCircle, Quote, RefreshCw, Sparkles, ThumbsUp } from 'lucide-react'
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
// Messages shown while Ollama works, chosen by elapsed seconds.
const waitingMessages = [
  [0, 'Estamos explorando tu afinidad con esta obra, espera un momento…'],
  [8, 'Hojeando tu valoración y tus notas de lectura…'],
  [18, 'Subrayando los pasajes que más te marcaron…'],
  [30, 'Conectando emociones, personajes y ritmo de la historia…'],
  [45, 'Escribiendo el último capítulo de tu análisis…'],
  [70, 'Esta lectura está tomando más de lo habitual. Puedes seguir en tu libro; el análisis aparecerá aquí al terminar.'],
]
const sourcesOf = claim => [...new Set(claim.evidence_ids.map(id => sourceLabels[id.split(':')[0]] || 'Registro propio'))].join(' · ')

function StatusBar({ analysis, working, failed, message, error }) {
  const state = working ? 'working' : failed || error ? 'failed' : 'done'
  const StateIcon = { working: LoaderCircle, failed: CircleAlert, done: CheckCircle2 }[state]
  if (!working && !message && !error) return null
  return <div className={`dna-status is-${state}`}>
    <div className="dna-status-row">
      <p role={state === 'failed' ? 'alert' : 'status'} aria-live={state === 'failed' ? 'assertive' : 'polite'}>
        <StateIcon className={state === 'working' ? 'dna-spinner' : undefined} size={20} aria-hidden="true" />
        <strong>{error || message}</strong>
      </p>
      {state === 'done' && analysis?.source_cutoff_at && <small className="bx-sync">Datos al {formatAnalysisDate(analysis.source_cutoff_at)}</small>}
    </div>
  </div>
}

function WaitingFindings() {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const started = Date.now()
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [])
  const text = waitingMessages.findLast(([from]) => seconds >= from)[1]
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

export default function BookExperience({ workId, data, analysis, working, failed, message, error, notice, onRefresh, submitting, information, setInformation, onFeedback }) {
  const { getBook } = useLibrary()
  const book = getBook(workId)
  const content = analysis?.content
  const findings = content ? groups.flatMap(([key, label, icon]) => (content[key] || []).map((claim, index) => ({ claim, label, icon, key: `${key}-${index}` }))) : []
  return <section className="book-experience-view" aria-label="Análisis personal de esta obra">
    <header className="dna-header">
      <div><span className="dna-kicker">Solo este libro</span><h2>Tu experiencia con este libro</h2><p>Interpretación privada de tu valoración y tus aportes sobre esta obra.</p></div>
      <button type="button" className="dna-refresh" disabled={working} onClick={onRefresh}><RefreshCw size={15} aria-hidden="true" />{working ? 'Procesando…' : failed ? 'Reintentar análisis' : 'Actualizar análisis'}</button>
    </header>
    {data?.status === 'awaiting_rating' && <p className="dna-notice">Valora este libro para ver su análisis individual aquí.</p>}
    <StatusBar analysis={analysis} working={working} failed={failed} message={message} error={error} />
    {notice && <p className="dna-notice" role="status">{notice}</p>}
    {working && analysis && <p className="dna-muted">Mientras se procesa la actualización, puedes consultar la última versión válida.</p>}
    {/* A newly rated book has no previous version yet, so the wait gets its own card. */}
    {working && data && !content && <article className="dna-card bx-result">
      <WorkHeading book={book} />
      <WaitingFindings />
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
