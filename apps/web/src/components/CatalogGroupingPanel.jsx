import { useRef, useState } from 'react'
import { apiRequest } from '../api/client'
import { useAuth } from '../context/AuthContext'
import '../pages/AdminCatalogPage.css'

const reviewStates = { published: 'Pública', hidden: 'Oculta', draft: 'Borrador' }
const operationLabels = { merge: 'Fusión', reversal: 'Reversión' }
const impactLabels = { library_entries: 'Entradas de biblioteca', shared_libraries: 'Bibliotecas con ambas obras', unique_readers: 'Lectores afectados', reading_attempts: 'Intentos de lectura', rereads: 'Relecturas actuales', editions: 'Ediciones conservadas', reviews: 'Reseñas conservadas', ratings: 'Valoraciones registradas' }

function WorkComparison({ label, side }) {
  return <article className="catalog-panel"><span className="catalog-eyebrow">{label}</span>
    <h2>{side.works?.find(work => work.id === side.canonical_id)?.title || side.works?.[0]?.title || 'Obra seleccionada'}</h2>
    <p>{side.authors?.map(author => author.name).filter((name,index,all) => all.indexOf(name)===index).join(', ') || 'Sin autores registrados'}</p>
    <dl className="catalog-metadata"><div><dt>Ediciones</dt><dd>{side.editions?.length || 0}</dd></div></dl>
    <ul className="catalog-editions">{side.editions?.map(edition => <li key={edition.id}><strong>{edition.title}</strong><span>{[edition.language,edition.publisher_name,edition.publication_date || edition.publication_year].filter(Boolean).join(' · ') || 'Sin datos de publicación'}</span><small>ISBN: {edition.isbn13 || edition.isbn10 || 'Sin registrar'}</small></li>)}</ul>
    <details><summary>Fuentes de las ediciones</summary><p>{[...new Set((side.sources || []).map(source => ({ 'google-books': 'Google Books', 'open-library': 'Open Library', 'libria-feed': 'LibrIAverse', 'libria-editorial': 'Corrección administrativa' })[source.provider] || source.provider))].join(' · ') || 'Registro de LibrIAverse'}</p></details>
  </article>
}

export default function CatalogGroupingPanel({ initialWorks = [], onComplete, embedded = false }) {
  const { access } = useAuth()
  const [query, setQuery] = useState('')
  const [works, setWorks] = useState([])
  const [knownWorks,setKnownWorks] = useState(() => Object.fromEntries(initialWorks.map(work => [work.id, work])))
  const [searched,setSearched] = useState(false)
  const [historyLoaded,setHistoryLoaded] = useState(false)
  const [source, setSource] = useState(initialWorks[0]?.id || '')
  const [target, setTarget] = useState(initialWorks[1]?.id || '')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState({})
  const [reason,setReason] = useState('')
  const [confirmation,setConfirmation] = useState('')
  const [policies,setPolicies] = useState(false)
  const [history,setHistory] = useState([])
  const [receipt,setReceipt] = useState(null)
  const [recovery,setRecovery] = useState(null)
  const [preserved,setPreserved] = useState({})
  const executionRequest=useRef(null)
  async function request(path, body, key) {
    setBusy(true); setError('')
    try {
      return await apiRequest(`/admin/catalog${path}`, { headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}`, ...(key ? { 'Idempotency-Key':key } : {}) },
        ...(body ? { method: 'POST', body: JSON.stringify(body) } : {}) })
    } catch (e) { setError(e.message); return null }
    finally { setBusy(false) }
  }
  async function compare(simulate) {
    setResult(null);setSelected({});setReceipt(null);setRecovery(null);setConfirmation('');setPolicies(false)
    setResult(await request(simulate ? '/merge-previews' : '/compare', { source_work_id: source, target_work_id: target }))
  }
  async function execute(reversal=false) {
    const body=reversal ? { confirmation,reason,preserve_physical:Object.keys(preserved).filter(key=>preserved[key]) }
      : { confirmation,reason,metadata_policy:'preserve_destination',library_policy:'preserve_all',review_ids:Object.values(selected) }
    const path=reversal ? `/reversal-previews/${recovery.preview_id}/execute` : `/merge-previews/${result.preview_id}/execute`
    const signature=JSON.stringify({path,body})
    if(executionRequest.current?.signature!==signature) executionRequest.current={signature,key:crypto.randomUUID()}
    const response=await request(path,body,executionRequest.current.key)
    if(response) {
      setReceipt(response);setResult(null);setRecovery(null);setConfirmation('');setPolicies(false)
      setHistory(await request('/history') || [])
      window.dispatchEvent(new Event('libria:book-activity-changed'))
      window.dispatchEvent(new Event('libria:catalog-identity-changed'))
      onComplete?.()
    }
  }
  function select(id, side) { side === 'source' ? setSource(id) : setTarget(id); setResult(null);setRecovery(null);setReceipt(null) }
  if (!access?.catalog_preview) return <p>Comparación administrativa deshabilitada.</p>
  const Heading = embedded ? 'h2' : 'h1'
  return <section className={`admin-catalog ${embedded ? 'catalog-grouping-embedded' : ''}`} aria-busy={busy}>
    <header className="catalog-header"><div><span className="catalog-eyebrow">Agrupación de libros y ediciones</span><Heading>Comparación de obras</Heading>
    <p>Busca dos registros que puedan representar el mismo libro y revisa sus diferencias antes de decidir si corresponde unirlos.</p></div>
    <button className="catalog-secondary" disabled={busy} onClick={async()=>{setHistory(await request('/history') || []);setHistoryLoaded(true)}}>Consultar historial administrativo</button></header>
    <ol className="catalog-steps"><li><span>1</span>Busca por título</li><li><span>2</span>Selecciona las dos obras</li><li><span>3</span>Compara y simula</li></ol>
    <section className="catalog-panel catalog-search" aria-labelledby="catalog-search-title">
    <h2 id="catalog-search-title">Encuentra las obras</h2>
    <form onSubmit={async e => { e.preventDefault();const items=await request(`/works?q=${encodeURIComponent(query.trim())}`);if(items){setWorks(items);setKnownWorks(current=>({...current,...Object.fromEntries(items.map(work=>[work.id,work]))}));setSearched(true)} }}>
      <label htmlFor="catalog-title-query">Título del libro<input id="catalog-title-query" type="search" placeholder="Ej.: Cien años de soledad" aria-describedby="catalog-search-help" value={query} maxLength={200} onChange={e => setQuery(e.target.value)} /></label>
      <button className="catalog-primary" disabled={busy || !query.trim()}>Buscar</button>
    </form>
    <p id="catalog-search-help" className="catalog-help">Escribe el título completo o una parte. Solo se buscan obras ya guardadas en LibrIAverse. Puedes hacer otra búsqueda para encontrar la segunda obra sin perder tu selección.</p>
    {searched && <p className="catalog-result-count" role="status">{works.length ? `${works.length} ${works.length===1?'obra encontrada':'obras encontradas'}` : 'No encontramos obras con ese título. Prueba con una parte del nombre.'}</p>}
    {!!works.length && <ul className="catalog-results">{works.map(w => <li key={w.id}><div><strong>{w.title}</strong><small>{w.id}</small></div>
      <div className="catalog-row-actions"><button aria-pressed={source===w.id} disabled={busy || target===w.id} onClick={() => select(w.id,'source')}>Seleccionar origen</button>
      <button aria-pressed={target===w.id} disabled={busy || source===w.id} onClick={() => select(w.id,'target')}>Seleccionar destino canónico</button></div>
    </li>)}</ul>}
    </section>
    <section className="catalog-panel" aria-labelledby="catalog-selection-title"><h2 id="catalog-selection-title">Obras que vas a comparar</h2>
    <div className="catalog-selection-grid">{[['Origen',source,'El registro que se vinculará a la obra principal. Su historial se conserva.'],['Destino canónico',target,'La obra principal que se mostrará en el catálogo después de la fusión.']].map(([label,id,help])=><div className={`catalog-selection ${id?'is-selected':''}`} key={label}><span className="catalog-eyebrow">{label}</span><strong>{knownWorks[id]?.title || 'Sin seleccionar'}</strong>{id && <small>{id}</small>}<p>{help}</p></div>)}</div>
    <div className="catalog-actions"><button className="catalog-primary" disabled={busy || !source || !target || source===target} onClick={() => compare(false)}>Comparar</button>
    <button disabled={busy || !source || !target || source===target} onClick={() => compare(true)}>Simular fusión</button></div>
    <p className="catalog-help">{!source || !target ? 'Selecciona un origen y un destino en los resultados para continuar.' : 'Compara los datos y luego simula el impacto. Ninguna de estas acciones ejecuta la fusión.'} Coincidir en título y autor no confirma identidad.</p></section>
    {error && <p role="alert">{error}</p>}
    {receipt && <p role="status">Operación {receipt.operation_id}: {receipt.status}. Los registros históricos se conservan.</p>}
    {result && <>
      <div className="catalog-comparison-grid">{[['Origen',result.source],['Destino',result.target]].map(([label,side]) => <WorkComparison key={label} label={label} side={side} />)}</div>
      <article className="catalog-panel"><h2>Impacto previsto</h2><dl className="catalog-impact-grid">{Object.entries(impactLabels).filter(([key])=>result.impact[key]!=null).map(([key,label])=><div key={key}><dt>{label}</dt><dd>{result.impact[key]}</dd></div>)}</dl><p className="catalog-help">Los registros históricos se conservan. Las valoraciones vigentes dependerán de la resolución de conflictos.</p></article>
      <article className="catalog-panel"><h2>Evidencias y conflictos</h2><p>{result.conflicts.length ? `${result.conflicts.length} conflictos de reseñas requieren una selección explícita.` : 'No se detectaron conflictos de reseñas entre las obras.'}</p><p className="catalog-help">Revisa autores, ediciones y fuentes. Las diferencias bibliográficas deben verificarse antes de confirmar.</p>
      {!!result.evidence?.contradictions?.length && <p className="catalog-help">Hay diferencias en los datos de las fichas. Comprueba los autores, los ISBN y los títulos de las ediciones antes de continuar.</p>}</article>
      {result.preview_id && <div className="catalog-help catalog-preview-note">Simulación lista. Válida hasta {new Date(result.expires_at).toLocaleString('es-CL')}.<details><summary>Ver identificador y huella de la simulación</summary><small>{result.preview_id} · {result.fingerprint}</small></details></div>}
      {result.preview_id && access?.catalog_merge && <fieldset disabled={busy}>
        <legend>Resolución explícita de conflictos</legend>
        {result.conflicts.map((conflict,i)=><fieldset key={i}><legend>Reseñas del mismo perfil: conflicto {i+1}</legend>
          <p>Seleccione una vigente. Se conservan ambas y sus estados; una selección oculta o borrador no será pública.</p>
          {conflict.review_ids.map(id=><label key={id} style={{display:'block'}}><input type="radio" name={`review-${i}`} value={id}
            checked={selected[i]===id} onChange={()=>setSelected({...selected,[i]:id})} />{id} — {reviewStates[result.impact.reviews_without_body.find(r=>r.id===id)?.status] || 'Estado sin registrar'}
            {conflict.proposed_review_id===id && ' (propuesta por última actualización; requiere su elección)'}</label>)}
        </fieldset>)}
        <label><input type="checkbox" checked={policies} onChange={e=>setPolicies(e.target.checked)} />Conservar metadatos del destino, todas las entradas y ediciones físicas. He revisado las evidencias bibliográficas.</label>
        <label>Motivo de la fusión<textarea placeholder="Explica qué evidencia confirma que se trata de la misma obra." value={reason} maxLength={2000} onChange={e=>setReason(e.target.value)} /></label>
        <label>Escribe FUSIONAR para confirmar<input placeholder="FUSIONAR" autoComplete="off" value={confirmation} onChange={e=>setConfirmation(e.target.value)} /></label>
        <button disabled={!policies || !reason.trim() || confirmation!=='FUSIONAR' || Object.keys(selected).length!==result.conflicts.length} onClick={()=>execute()}>Confirmar fusión administrativa</button>
      </fieldset>}
    </>}
    {(historyLoaded || !!history.length) && <article className="catalog-panel catalog-history"><h2>Historial administrativo</h2>{!history.length && <p className="catalog-help">Todavía no hay fusiones o reversiones registradas.</p>}<ul>{history.map(op=><li key={op.id}><div><strong>{operationLabels[op.kind] || op.kind}</strong><p>{op.reason}</p><small>{op.created_at ? new Date(op.created_at).toLocaleString('es-CL')+' · ' : ''}{op.id}</small></div>
      {op.kind==='merge' && op.active && access?.catalog_merge && <button disabled={busy} onClick={async()=>{
        setResult(null);setReceipt(null);setPreserved({});setConfirmation('');setRecovery(await request(`/merges/${op.id}/reversal-preview`,{}))
      }}>Simular reversión</button>}</li>)}</ul></article>}
    {recovery && <article><h2>Simulación de separación</h2><p>{recovery.policy}</p>
      {recovery.blockers.map((b,i)=><p role="alert" key={i}>{b.entity}: {b.reason}</p>)}
      {recovery.changes.map(change=><label key={change.entity} style={{display:'block'}}><input type="checkbox" checked={!!preserved[change.entity]}
        onChange={e=>setPreserved({...preserved,[change.entity]:e.target.checked})} />Conservar {change.entity} ({change.change}) con su atribución física {change.physical_work_id || 'compartida/original'}{change.attribution==='requires_explicit_physical_attribution' && ' — La referencia solicitada difiere: revise la procedencia antes de aceptar.'}</label>)}
      <pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(recovery.provenance,null,2)}</pre>
      <label>Motivo de reversión<textarea placeholder="Explica por qué se deben volver a separar estas obras." value={reason} maxLength={2000} onChange={e=>setReason(e.target.value)} /></label>
      <label>Escribe REVERTIR para confirmar<input placeholder="REVERTIR" autoComplete="off" value={confirmation} onChange={e=>setConfirmation(e.target.value)} /></label>
      <button disabled={busy || !recovery.can_execute || !reason.trim() || confirmation!=='REVERTIR' || recovery.changes.some(c=>!preserved[c.entity])} onClick={()=>execute(true)}>Confirmar reversión administrativa</button>
    </article>}
  </section>
}
