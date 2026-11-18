import { useState } from 'react'
import { formatAnalysisDate } from './adaptiveAnalysisLabels'
import ReaderEssence from './ReaderEssence'
import DnaProfileSections from './DnaProfileSections'

const dimensions = [
  ['narrative_preferences', 'Preferencias narrativas'], ['character_preferences', 'Personajes'],
  ['themes_and_conflicts', 'Temas y conflictos'], ['emotional_patterns', 'Respuestas expresadas'],
  ['rating_patterns', 'Patrones de valoración'], ['genres_and_styles', 'Géneros y estilos'],
  ['interests_from_notes_and_theories', 'Intereses en notas'],
]
const comparable = content => content?.reader_essence?.evidence_level === 'sufficient'

export default function ReaderDnaEvolution({ content, currentId, currentAnalysisId, history, busy, onLoad }) {
  const [selectedId, setSelectedId] = useState('')
  const evolution = content?.evolution
  const selected = history?.find(item => item.id === selectedId)
  const comparisons = history?.filter(item => item.id !== currentAnalysisId && item.dna_version_id !== currentId && comparable(item.content)) || []
  return <section className="dna-card dna-evolution" aria-label="La evolución de tu ADN">
    <h3>La evolución de tu ADN</h3>
    <p>{evolution?.summary || 'Tu evolución todavía se está construyendo. Necesitamos al menos dos versiones con suficiente evidencia para comparar tus preferencias.'}</p>
    {evolution && <div className="dna-evolution-patterns">{[
      ['stable_patterns', 'Lo que se mantiene'], ['emerging_interests', 'Lo que está emergiendo'], ['changing_preferences', 'Cambios respaldados'],
    ].map(([key, label]) => evolution[key]?.length > 0 && <div key={key}><h4>{label}</h4><ul>{evolution[key].map((claim, index) => <li key={index}>{claim.text}</li>)}</ul></div>)}</div>}
    <button type="button" className="button secondary" disabled={busy} onClick={() => onLoad()}>{busy ? 'Consultando versiones…' : 'Consultar historial privado'}</button>
    {history && <>{history.length === 0 ? <p className="dna-muted">Aún no hay versiones guardadas.</p> : <ol className="dna-timeline">{history.map(item => <li key={item.id}>
      <strong>{formatAnalysisDate(item.created_at)}</strong><span>Versión {item.version} · {item.content?.reader_essence?.archetype || 'ADN lector'}</span>
      <p>{item.content?.evolution?.summary || (item.content?.reader_essence ? 'Punto de referencia de tus preferencias literarias.' : 'Versión anterior a la interpretación profunda.')}</p>
      <details><summary>Ver esta versión</summary><ReaderEssence essence={item.content?.reader_essence} />
        {item.content?.narrative_preferences ? <DnaProfileSections content={item.content} /> : <p>{item.content?.interpretation || 'Análisis anterior del perfil lector.'}</p>}</details>
    </li>)}</ol>}
      {history.length >= 20 && <button type="button" className="button secondary" disabled={busy} onClick={() => onLoad(history.at(-1).version)}>Ver versiones anteriores</button>}
      {comparable(content) && comparisons.length > 0 && <div className="dna-version-comparison">
        <label>Comparar con una versión anterior<select value={selectedId} onChange={event => setSelectedId(event.target.value)}><option value="">Selecciona una versión</option>{comparisons.map(item => <option key={item.id} value={item.id}>Versión {item.version} · {formatAnalysisDate(item.created_at)}</option>)}</select></label>
        {selected && <><p>Compara los hallazgos guardados. Una redacción distinta por sí sola no demuestra un cambio de preferencias.</p>
          <div className="dna-comparison-head"><strong>Versión {selected.version}</strong><strong>Versión actual</strong></div>
          {dimensions.map(([key, label]) => <section key={key} className="dna-comparison-dimension"><h4>{label}</h4><div className="dna-comparison-columns">{[selected.content, content].map((version, index) => <div key={index}><span className="dna-kicker">{index === 0 ? 'Anterior' : 'Actual'}</span>{version[key]?.length ? <ul>{version[key].map((text, itemIndex) => <li key={itemIndex}>{text}</li>)}</ul> : <p>Sin hallazgos respaldados.</p>}</div>)}</div></section>)}
        </>}
      </div>}
    </>}
  </section>
}
