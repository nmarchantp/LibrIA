import { useEffect, useId, useState } from 'react'
import { BadgeCheck, BookX, CheckCircle2, ChevronDown, CircleAlert, Clock3, Compass, Heart, LoaderCircle, Quote, RefreshCw, Repeat, SlidersHorizontal, Sparkles, ThumbsDown, ThumbsUp } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiRequest } from '../api/client'
import { useLibrary } from '../context/LibraryContext'
import BookCover from './BookCover'
import RatingStar from './RatingStar'
import { presentBookCategories } from './bookCategories'
import { formatAnalysisDate, sourceLabels } from './adaptiveAnalysisLabels'
import './ReaderDna.css'

// Each AI claim group becomes a card category; only data returned by the API is shown.
const groups = [
  ['historical_affinities', 'Preferencias que se repiten', Repeat],
  ['recent_affinities', 'Lo que valoras últimamente', Clock3],
  ['exploratory_interests', 'Lo que estás explorando', Compass],
  ['satisfaction_factors', 'Lo que más disfrutas', Heart],
  ['abandonment_factors', 'Lo que dificulta continuar', BookX],
  ['confirmed_preferences', 'Lo que tú confirmaste', BadgeCheck],
]
const kinds = {
  pattern: { badge: 'Patrón recurrente', filter: 'Patrones', icon: CheckCircle2 },
  emerging: { badge: 'Señal emergente', filter: 'Emergentes', icon: CircleAlert },
  confirmed: { badge: 'Confirmado por ti', filter: 'Confirmadas', icon: BadgeCheck },
}
const statusClasses = { Terminado: 'finished', Leyendo: 'reading', Abandonado: 'abandoned' }
const plural = (count, one, many) => `${count} ${count === 1 ? one : many}`
const formatRating = value => new Intl.NumberFormat('es-CL', { maximumFractionDigits: 2 }).format(value)

// Books cited by a set of evidence keys, one entry per work.
function citedWorks(evidence, keys) {
  const works = new Map()
  for (const source of evidence) {
    if (keys.includes(source.source_key) && source.work_id && source.book_title && !works.has(source.work_id)) works.set(source.work_id, { id: source.work_id, title: source.book_title })
  }
  return [...works.values()]
}

// The reader's own rating per work, read from the existing reviews endpoint.
function useOwnRatings(workIds) {
  const key = workIds.join(',')
  const [ratings, setRatings] = useState({})
  useEffect(() => {
    if (!key) return
    let active = true
    const headers = { Authorization: `Bearer ${localStorage.getItem('libria_token')}` }
    Promise.all(key.split(',').map(id => apiRequest(`/reviews/me?work_id=${id}`, { headers })
      .then(items => [id, items[0]?.rating ?? null]).catch(() => [id, null])))
      .then(entries => { if (active) setRatings(Object.fromEntries(entries)) })
    return () => { active = false }
  }, [key])
  return ratings
}

function StatusBar({ data, analysis, content, working, failed, message, error, onRefresh }) {
  const [open, setOpen] = useState(false)
  const panelId = useId()
  const summary = data?.library_summary
  const state = working ? 'working' : failed || error ? 'failed' : 'done'
  const StateIcon = { working: LoaderCircle, failed: CircleAlert, done: CheckCircle2 }[state]
  return <div className={`dna-status is-${state}`}>
    <div className="dna-status-row">
      <p role={state === 'failed' ? 'alert' : 'status'} aria-live={state === 'failed' ? 'assertive' : 'polite'}>
        <StateIcon className={state === 'working' ? 'dna-spinner' : undefined} size={20} aria-hidden="true" />
        <span><strong>{error || message || (analysis ? 'Análisis disponible' : 'Sin análisis todavía')}</strong>
          {state === 'done' && summary?.rated > 0 && <small>Basado en tus {plural(summary.rated, 'valoración', 'valoraciones')}</small>}</span>
      </p>
      <div className="dna-status-actions">
        {content && <button type="button" className="dna-link-button" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(value => !value)}>Detalles de cálculo<ChevronDown size={15} aria-hidden="true" /></button>}
        <button type="button" className="dna-refresh" disabled={working} onClick={onRefresh}><RefreshCw size={15} aria-hidden="true" />Actualizar estado</button>
      </div>
    </div>
    {content && open && <div className="dna-details" id={panelId}>
      <dl>
        <div><dt>Versión</dt><dd>{analysis.version}</dd></div>
        <div><dt>Generado</dt><dd>{formatAnalysisDate(analysis.created_at)}</dd></div>
        {analysis.source_cutoff_at && <div><dt>Datos al</dt><dd>{formatAnalysisDate(analysis.source_cutoff_at)}</dd></div>}
        <div><dt>Modelo</dt><dd>{analysis.model}</dd></div>
        {summary && <div><dt>Tu biblioteca</dt><dd>{summary.finished} terminados · {summary.reading} leyendo · {summary.abandoned} abandonados</dd></div>}
      </dl>
      <h4>Evidencias consideradas</h4>
      <ul>{data.evidence.map(item => <li key={item.source_key}>{sourceLabels[item.source_kind] || 'Registro propio'} · {item.book_title || <code>{item.source_id}</code>}</li>)}</ul>
      <h4>Límites de esta versión</h4>
      <ul>{content.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>
      <p>Estas son interpretaciones de IA sobre registros de lectura. No describen tu personalidad ni tu salud mental.</p>
    </div>}
  </div>
}

function SupportingBook({ work, book, rating }) {
  const cover = book || { title: work.title, initial: work.title.charAt(0).toUpperCase() }
  const body = <>
    <BookCover book={cover} />
    <span className="dna-book-copy">
      <span className="dna-book-badges"><span>Lectura base</span>{book?.status && <span className={`dna-book-status ${statusClasses[book.status] || ''}`}>{book.status}</span>}</span>
      <strong>{work.title}</strong>
      {book?.author && <small>{book.author}</small>}
    </span>
    {rating != null && <span className="dna-book-rating" aria-label={`Tu valoración: ${formatRating(rating)} de 5`}><RatingStar selected size={14} />{formatRating(rating)}</span>}
  </>
  return book ? <Link className="dna-book" to={`/library/${encodeURIComponent(book.id)}`}>{body}</Link> : <div className="dna-book">{body}</div>
}

function IdentityCard({ content, evidence }) {
  const { getBook } = useLibrary()
  const works = citedWorks(evidence, content.identity_evidence_ids || [])
  const ratings = useOwnRatings(works.map(work => work.id))
  const books = works.map(work => getBook(work.id))
  // Tags come from the catalog genres of the supporting books, not from the AI.
  const tags = presentBookCategories(...books.map(book => book?.categories || [])).filter(category => category.family !== 'neutral').slice(0, 4)
  return <article className="dna-card dna-identity">
    <header className="dna-card-heading">
      <div><span className="dna-kicker">Esencia narrativa</span><h3>Tu identidad literaria</h3></div>
      {tags.length > 0 && <ul className="dna-tags" aria-label="Géneros de las lecturas que respaldan tu identidad">{tags.map(tag => <li key={tag.label}>{tag.label}</li>)}</ul>}
    </header>
    <blockquote className="dna-quote"><p>“{content.literary_identity}”</p></blockquote>
    <div className="dna-subheading"><span className="dna-kicker">Lecturas que respaldan esta identidad</span>{works.length > 0 && <small>{plural(works.length, 'libro vinculado', 'libros vinculados')}</small>}</div>
    {works.length ? <ul className="dna-book-grid">{works.map((work, index) => <li key={work.id}><SupportingBook work={work} book={books[index]} rating={ratings[work.id]} /></li>)}</ul>
      : <p className="dna-muted">Aún se necesitan más experiencias valoradas.</p>}
  </article>
}

function AffinityCard({ claim }) {
  const { badge, icon: BadgeIcon } = kinds[claim.kind]
  const Icon = claim.icon
  const evidenceText = claim.kind === 'pattern' ? `Confirmado en ${claim.works.length} libros` : claim.kind === 'emerging' ? 'Señal de una sola obra; todavía no confirma una preferencia que se repita.' : 'Basado en lo que tú confirmaste o corregiste.'
  return <article className={`dna-card dna-affinity is-${claim.kind}`}>
    <header>
      <span className="dna-affinity-category"><span className="dna-icon"><Icon size={16} aria-hidden="true" /></span>{claim.label}</span>
      <span className={`dna-badge is-${claim.kind}`}><BadgeIcon size={13} aria-hidden="true" />{badge}</span>
    </header>
    <p className="dna-affinity-text">{claim.text}</p>
    <p className="dna-evidence"><strong>Evidencia detectada:</strong> {evidenceText}</p>
    {claim.works.length > 0 && <footer><span>Se observa en:</span><ul>{claim.works.map(work => <li key={work.id} title={work.title}>{work.title}</li>)}</ul></footer>}
  </article>
}

function Affinities({ claims }) {
  const headingId = useId()
  const [filter, setFilter] = useState('all')
  const counts = { all: claims.length }
  for (const claim of claims) counts[claim.kind] = (counts[claim.kind] || 0) + 1
  const active = counts[filter] ? filter : 'all'
  const filters = [['all', 'Todas'], ...Object.entries(kinds).filter(([kind]) => counts[kind]).map(([kind, { filter: label }]) => [kind, label])]
  const visible = active === 'all' ? claims : claims.filter(claim => claim.kind === active)
  return <section className="dna-affinities" aria-labelledby={headingId}>
    <div className="dna-section-heading">
      <div><h3 id={headingId}>Afinidades detectadas</h3><p>Lo que disfrutas de los temas, personajes, mundos y estilos según tus lecturas y aportes.</p></div>
      {filters.length > 2 && <div className="dna-filter" role="group" aria-label="Filtrar afinidades">
        <span><SlidersHorizontal size={14} aria-hidden="true" />Filtrar:</span>
        {filters.map(([value, label]) => <button key={value} type="button" className={active === value ? 'active' : ''} aria-pressed={active === value} onClick={() => setFilter(value)}>{label} ({counts[value]})</button>)}
      </div>}
    </div>
    {claims.length ? <ul className="dna-affinity-grid">{visible.map(claim => <li key={claim.key}><AffinityCard claim={claim} /></li>)}</ul>
      : <p className="dna-empty">Aún no hay afinidades suficientemente respaldadas para mostrarlas.</p>}
  </section>
}

function GlobalCard({ content, claims }) {
  const distribution = groups.map(([key, label]) => ({ key, label, count: claims.filter(claim => claim.group === key).length })).filter(item => item.count).sort((a, b) => b.count - a.count)
  // Equal bars carry no information, so the chart only appears when groups differ.
  const showDistribution = distribution.length > 1 && distribution[0].count > distribution.at(-1).count
  return <article className="dna-card dna-global">
    <span className="dna-kicker"><Quote size={13} aria-hidden="true" />Interpretación global de tu perfil</span>
    <h3>Tu perfil en conjunto</h3>
    <p className="dna-global-text">{content.interpretation}</p>
    <p className="dna-refine"><Sparkles size={15} aria-hidden="true" />Este perfil se actualiza cuando valoras o comentas un libro.</p>
    {showDistribution && <div className="dna-distribution">
      <span className="dna-kicker">Distribución de afinidades</span>
      <ul>{distribution.map(item => <li key={item.key}>
        <span className="dna-distribution-label"><span>{item.label}</span><strong>{plural(item.count, 'afinidad', 'afinidades')}</strong></span>
        <span className="dna-bar" aria-hidden="true"><span style={{ width: `${item.count / claims.length * 100}%` }} /></span>
      </li>)}</ul>
    </div>}
  </article>
}

function FeedbackCard({ working, submitting, information, setInformation, onFeedback }) {
  return <article className="dna-card dna-feedback">
    <div className="dna-feedback-heading">
      <div><h3>¿Te representa este análisis?</h3><p>Tu respuesta tendrá prioridad en la próxima interpretación.</p></div>
      <div className="dna-feedback-actions">
        <button className="button secondary" type="button" disabled={working} onClick={() => onFeedback('confirm')}><ThumbsUp size={16} aria-hidden="true" />Me representa</button>
        <button className="button secondary" type="button" disabled={working} onClick={() => onFeedback('reject')}><ThumbsDown size={16} aria-hidden="true" />No me representa</button>
      </div>
    </div>
    <form onSubmit={event => { event.preventDefault(); onFeedback('correct') }}>
      <label>¿Hay algo que corregir?<textarea maxLength={3000} rows={3} disabled={submitting} value={information} onChange={event => setInformation(event.target.value)} placeholder="Explica qué interpretó mal la IA o confirma qué preferencias sí te representan." /></label>
      <button className="button primary" disabled={working || !information.trim()}>Guardar corrección</button>
    </form>
  </article>
}

function GeminiProfile({ data, analysis, content, working, failed, message, error, notice, onRefresh,
  submitting, information, setInformation, onFeedback, history, historyBusy, onLoadHistory }) {
  const groups = [
    ['narrative_preferences', 'Preferencias narrativas'],
    ['character_preferences', 'Personajes'],
    ['themes_and_conflicts', 'Temas y conflictos'],
    ['genres_and_styles', 'Géneros y estilos'],
    ['emotional_patterns', 'Respuestas expresadas'],
    ['interests_from_notes_and_theories', 'Intereses en notas y teorías'],
    ['rating_patterns', 'Patrones de valoración'],
  ]
  return <section className="reader-dna-view" aria-label="Perfil lector persistido">
    <header className="dna-header"><div><span className="dna-kicker">Perfil nocturno</span><h2>ADN Lector &amp; Afinidades</h2><p>Interpretación Gemini vinculada al último perfil elegible del ETL.</p></div></header>
    <StatusBar data={data} analysis={analysis} content={null} working={working} failed={failed} message={message} error={error} onRefresh={onRefresh} />
    {notice && <p className="dna-notice" role="status">{notice}</p>}
    <div className="dna-affinity-grid">{groups.map(([key, label]) => <article className="dna-card" key={key}><h3>{label}</h3>
      {content[key]?.length ? <ul>{content[key].map((item, index) => <li key={index}>{item}</li>)}</ul> : <p className="dna-muted">Sin hallazgos suficientemente respaldados.</p>}
    </article>)}</div>
    <details className="dna-card"><summary>Evidencias y metadatos</summary><p>Modelo: {analysis.model}</p><p>Generado: {formatAnalysisDate(analysis.created_at)}</p>
      <p>{content.evidence_ids.length} referencia(s) validadas; solo la titular puede consultar este resultado.</p></details>
    <FeedbackCard working={working} submitting={submitting} information={information} setInformation={setInformation} onFeedback={onFeedback} />
    <div className="dna-history"><button className="button secondary" disabled={historyBusy || working} onClick={() => onLoadHistory()}>{historyBusy ? 'Consultando versiones…' : 'Consultar historial de versiones'}</button>
      {history && <ul>{history.map(item => <li key={item.id}><strong>Versión {item.version}</strong> · {formatAnalysisDate(item.created_at)}<p>{item.provider} · {item.model}</p></li>)}</ul>}
    </div>
  </section>
}

export default function ReaderDna({ data, analysis, working, failed, message, error, notice, onRefresh, submitting, information, setInformation, onFeedback, history, historyBusy, onLoadHistory }) {
  const summary = data?.library_summary
  const content = analysis?.content
  if (content?.narrative_preferences) return <GeminiProfile {...{data, analysis, content, working, failed, message, error, notice, onRefresh,
    submitting, information, setInformation, onFeedback, history, historyBusy, onLoadHistory}} />
  const evidence = data?.evidence || []
  const claims = content ? groups.flatMap(([group, label, icon]) => (content[group] || []).map((claim, index) => {
    const works = citedWorks(evidence, claim.evidence_ids)
    return { ...claim, key: `${group}-${index}`, group, label, icon, works, kind: works.length > 1 ? 'pattern' : works.length === 1 ? 'emerging' : 'confirmed' }
  })) : []
  return <section className="reader-dna-view" aria-label="ADN lector global">
    <header className="dna-header">
      <div><span className="dna-kicker">Diagnóstico literario continuo</span><h2>ADN Lector &amp; Afinidades</h2><p>Síntesis basada en tus calificaciones, reflexiones y patrones de lectura.</p></div>
      {summary && <ul className="dna-stats" aria-label="Resumen de tu biblioteca">
        <li><strong>{summary.total}</strong> {summary.total === 1 ? 'libro' : 'libros'}</li>
        <li><strong>{summary.rated}</strong> {summary.rated === 1 ? 'valorado' : 'valorados'}</li>
        <li><strong>{summary.pending}</strong> {summary.pending === 1 ? 'pendiente' : 'pendientes'}</li>
      </ul>}
    </header>
    <StatusBar data={data} analysis={analysis} content={content} working={working} failed={failed} message={message} error={error} onRefresh={onRefresh} />
    {notice && <p className="dna-notice" role="status">{notice}</p>}
    {working && analysis && <p className="dna-muted">Mientras se procesa la actualización, puedes consultar la última versión válida.</p>}
    {content && <>
      <IdentityCard content={content} evidence={evidence} />
      <Affinities claims={claims} />
      <GlobalCard content={content} claims={claims} />
      <FeedbackCard working={working} submitting={submitting} information={information} setInformation={setInformation} onFeedback={onFeedback} />
    </>}
    <div className="dna-history">
      <button className="button secondary" disabled={historyBusy || working} onClick={() => onLoadHistory()}>{historyBusy ? 'Consultando versiones…' : 'Consultar historial de versiones'}</button>
      {history && <><ul>{history.map(item => <li key={item.id}><strong>Versión {item.version}</strong> · {formatAnalysisDate(item.created_at)}<p>{item.valid && item.content.literary_identity ? item.content.interpretation : 'Versión anterior no vigente del perfil global.'}</p></li>)}</ul>
        {history.length > 0 && <button className="button" disabled={historyBusy} onClick={() => onLoadHistory(history.at(-1).version)}>Ver versiones anteriores</button>}</>}
    </div>
  </section>
}
