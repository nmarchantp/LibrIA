import { useEffect, useState } from 'react'
import { Database, RefreshCw, CheckCircle2, Clock3, AlertTriangle, Play } from 'lucide-react'
import { apiRequest } from '../api/client'
import './AdminEtlPage.css'

const labels = { succeeded: 'Completado', running: 'En ejecución', failed: 'Fallido' }
const phases = { queued: 'En cola', extracting: 'Extrayendo de app', transforming: 'Limpiando y validando', loading: 'Cargando en analytics', completed: 'Extracción, limpieza y carga completadas', failed: 'Proceso detenido' }
const rules = {
  invalid_work_title: 'Obras sin título válido', event_identity_mismatch: 'Eventos con relaciones inconsistentes',
  event_invalid_pages: 'Eventos con paginación inválida', event_invalid_date: 'Eventos con fechas incoherentes',
  event_invalid_transition: 'Eventos con transición incoherente', legacy_reading_post: 'Avances del feed antiguo: no son eventos verificables',
  review_model_pending: 'Reseñas: pendiente de normalizar su entidad', publication_missing_profile: 'Publicaciones sin perfil autor verificable',
  publication_invalid_contract: 'Publicaciones con contrato inconsistente', library_unknown_work: 'Incorporaciones sin obra válida',
  reconciliation: 'Conciliación de filas cargadas',
  review_invalid_identity: 'Reseñas con obra, edición o autoría incoherente',
  review_draft_not_published: 'Borradores: todavía no son reseñas publicadas',
  reflection_invalid_contract: 'Reflexiones excluidas por valores o estructura inválidos',
  review_invalid_revision: 'Reseñas con versión o fechas incoherentes',
}
const formatTime = value => value ? new Intl.DateTimeFormat('es-CL', {
  timeZone: 'America/Santiago', dateStyle: 'short', timeStyle: 'short',
}).format(new Date(value)) : '—'
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })

export default function AdminEtlPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [selected, setSelected] = useState(null)
  const [validations, setValidations] = useState(null)
  const [validationError, setValidationError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [starting, setStarting] = useState(false)
  const [manualError, setManualError] = useState('')
  const [manualRun, setManualRun] = useState(null)
  const [requestId, setRequestId] = useState(null)
  const running = data?.runs.some(run => run.status === 'running') || starting
  const shownRun = data?.runs.find(run => run.id === manualRun) || data?.runs.find(run => run.run_kind === 'manual')

  useEffect(() => {
    let active = true
    const load = () => {
      setRefreshing(true)
      apiRequest('/analytics/admin/etl', { headers: headers() }).then(result => {
        if (active) { setData(result); setError('') }
      }).catch(err => {
        if (active) setError(err.status === 403 ? 'Tu cuenta no tiene permiso para consultar el ETL.' : 'No se pudo consultar el ETL. Puedes volver a actualizar.')
      }).finally(() => { if (active) setRefreshing(false) })
    }
    load()
    const interval = setInterval(load, running ? 2000 : 30000)
    return () => { active = false; clearInterval(interval) }
  }, [refreshKey, running])

  useEffect(() => {
    if (!selected) return
    let active = true
    apiRequest(`/analytics/admin/etl/${selected}/validations`, { headers: headers() }).then(result => {
      if (active) setValidations(result)
    }).catch(() => { if (active) setValidationError('No se pudieron cargar las validaciones.') })
    return () => { active = false }
  }, [selected, refreshKey])

  function selectRun(id) {
    setValidations(null)
    setValidationError('')
    setSelected(id)
  }

  async function executeEtl() {
    setStarting(true)
    setManualError('')
    const id = requestId || crypto.randomUUID()
    setRequestId(id)
    try {
      const result = await apiRequest('/analytics/admin/etl/run', {
        method: 'POST', headers: headers(), body: JSON.stringify({ request_id: id }),
      })
      setManualRun(result.id)
      setRequestId(null)
      setRefreshKey(value => value + 1)
    } catch (err) {
      setManualError(err.status === 409 ? 'Ya hay un ETL en curso. Espera su finalización y actualiza el estado.' : err.status === 403 ? 'Tu cuenta no tiene permiso para ejecutar el ETL.' : 'No se pudo confirmar la solicitud. Puedes reintentar; se conservará el identificador para evitar una carga duplicada.')
      if (err.status === 409 || err.status === 403) setRequestId(null)
      setRefreshKey(value => value + 1)
    } finally { setStarting(false) }
  }

  return <section className="page-width page etl-page">
    <div className="etl-heading"><div><span className="kicker">ADMINISTRACIÓN</span><h1 className="page-title">Carga de datos diarios</h1><p className="page-lead">Seguimiento del proceso que valida y prepara los datos de LibrIA.</p></div>
      <button className="button secondary" disabled={refreshing} onClick={() => setRefreshKey(value => value + 1)}><RefreshCw size={17} />{refreshing ? 'Actualizando…' : 'Actualizar estado'}</button></div>
    {error && <div className="etl-warning" role="alert">{error}</div>}
    {!data && !error && <p role="status">Cargando estado del ETL…</p>}
    {data && <>
      <article className="etl-manual">
        <div className="etl-heading"><div><h2>Ejecutar ETL ahora</h2><p>Extrae los datos de los últimos 30 días, incluyendo hoy, valida y limpia las filas, y carga una instantánea real en el esquema analytics.</p></div>
          <button className="button primary" disabled={running} onClick={executeEtl}><Play size={17} />{running ? 'ETL en ejecución…' : 'Ejecutar ETL ahora'}</button></div>
        <p>Esta carga manual queda registrada por separado. El cierre diario sigue programado a las 00:00 y los indicadores personales utilizan los cierres diarios.</p>
        {manualError && <p className="etl-warning" role="alert">{manualError}</p>}
        {shownRun && <div className="etl-manual-result" role="status" aria-live="polite">
          <strong>{phases[shownRun.phase] || labels[shownRun.status]}</strong>
          <p>Origen: app → destino: analytics · Desde {formatTime(shownRun.period_start)} hasta {formatTime(shownRun.source_cutoff_at)} · ID: {shownRun.id}</p>
          {shownRun.status === 'failed' && <p>No se cargaron filas parciales. Puedes iniciar una nueva ejecución.{shownRun.error_code === 'etl_busy' ? ' Otro ETL estaba ejecutándose.' : ''}</p>}
          {shownRun.status === 'succeeded' && <>
            <div className="etl-table-wrap"><table className="etl-table"><caption>Resultado de extracción y carga</caption><thead><tr><th>Datos</th><th>Extraídos</th><th>Cargados</th></tr></thead><tbody>
              <tr><td>Eventos de lectura</td><td>{shownRun.summary.source_events}</td><td>{shownRun.summary.loaded_events}</td></tr>
              <tr><td>Publicaciones</td><td>{shownRun.summary.source_posts}</td><td>{shownRun.summary.loaded_posts}</td></tr>
              <tr><td>Reseñas</td><td>{shownRun.summary.source_reviews}</td><td>{shownRun.summary.loaded_reviews}</td></tr>
              {shownRun.summary.loaded_reflections !== undefined && <tr><td>Reflexiones privadas de lectura</td><td>{shownRun.summary.source_reflections}</td><td>{shownRun.summary.loaded_reflections}</td></tr>}
              <tr><td>Incorporaciones a biblioteca</td><td>{shownRun.summary.source_library_entries}</td><td>{shownRun.summary.loaded_library_entries} utilizadas para indicadores</td></tr>
            </tbody></table></div>
            <p>Limpieza: {shownRun.summary.excluded_rows} filas excluidas por las reglas. Carga: {shownRun.summary.catalog_rows} obras y {shownRun.summary.indicator_rows} indicadores preparados. Conciliación completada.</p>
            <button className="etl-link" onClick={() => selectRun(shownRun.id)}>Ver reglas de limpieza y validación</button>
          </>}
        </div>}
      </article>
      <div className={`etl-status ${data.up_to_date ? 'ready' : 'pending'}`}><CheckCircle2 size={22} /><div><strong>{data.up_to_date ? 'Datos actualizados al último cierre' : `${data.pending_days} cierres pendientes`}</strong><p>Último día cargado: {data.last_loaded_day || 'Todavía sin cargas'} · Último día cerrado: {data.latest_closed_day}</p></div></div>
      <div className="etl-cards">
        <article><Clock3 /><span>Cierre diario</span><strong>{data.schedule}</strong><small>{data.timezone} · {data.scheduler_enabled ? 'Programación activa con el servidor encendido' : 'Programación automática desactivada'}</small></article>
        <article><Database /><span>Eventos de lectura</span><strong>{data.counts.reading_rows}</strong><small>Registros validados en analytics</small></article>
        <article><Database /><span>Publicaciones</span><strong>{data.counts.publication_rows}</strong><small>Contenido manual validado</small></article>
        <article><Database /><span>Reseñas</span><strong>{data.counts.review_rows}</strong><small>Versiones preparadas al cierre diario</small></article>
        <article><Database /><span>Indicadores personales</span><strong>{data.counts.indicator_rows}</strong><small>Filas privadas de sus titulares</small></article>
      </div>
      <p className="etl-schedule">Próximo cierre: <strong>{formatTime(data.next_run_at)}</strong>. Cada cierre diario se carga una sola vez. Los totales incluyen las instantáneas manuales y diarias; no representan registros únicos. Si el servidor estuvo apagado, recupera los cierres diarios pendientes al iniciar.</p>
      {data.review_migration?.length > 0 && <p className="etl-schedule">Reseñas antiguas: <strong>{data.review_migration.filter(row => row.result === 'migrated').reduce((total, row) => total + row.total, 0)} migradas</strong> y <strong>{data.review_migration.filter(row => row.result === 'pending').reduce((total, row) => total + row.total, 0)} pendientes de identificar</strong>. Los casos pendientes se conservan y no se incluyen como reseñas válidas.</p>}
      <div className="etl-table-wrap"><table className="etl-table"><caption>Historial de cargas manuales y cierres diarios</caption><thead><tr><th>Día / tipo</th><th>Estado</th><th>Finalizó</th><th>Lecturas</th><th>Publicaciones</th><th>Reseñas</th><th>Exclusiones</th><th>Intentos</th><th>Validaciones</th></tr></thead><tbody>
        {data.runs.length === 0 && <tr><td colSpan={9}>Todavía no hay ejecuciones diarias.</td></tr>}
        {data.runs.map(run => <tr key={run.id}><td>{run.business_date || formatTime(run.started_at)}<small>{run.run_kind === 'manual' ? 'Manual' : 'Cierre diario'}</small></td><td><span className={`etl-badge ${run.status}`}>{labels[run.status] || run.status}</span>{run.error_code && <small className="etl-run-error">La carga falló; no se publicaron datos parciales.</small>}</td><td>{formatTime(run.finished_at)}</td><td>{run.status === 'succeeded' ? run.summary.loaded_events : '—'}{run.summary.simulated_events > 0 && <small>Incluye {run.summary.simulated_events} simulados</small>}</td><td>{run.status === 'succeeded' ? run.summary.loaded_posts : '—'}</td><td>{run.status === 'succeeded' ? (run.summary.loaded_reviews ?? 'No incluido') : '—'}{run.summary.simulated_reviews > 0 && <small>Incluye {run.summary.simulated_reviews} simuladas</small>}</td><td>{run.status === 'succeeded' ? run.summary.excluded_rows : '—'}</td><td>{run.attempt_count}</td><td><button className="etl-link" onClick={() => selectRun(run.id)}>Ver reglas</button></td></tr>)}
      </tbody></table></div>
      {selected && <article className="etl-validations"><div className="etl-heading"><h2>Validaciones de la ejecución {data.runs.find(run => run.id === selected)?.business_date || 'manual'}</h2><button className="etl-link" onClick={() => setSelected(null)}>Cerrar detalle</button></div>
        {validationError && <p role="alert">{validationError}</p>}
        {!validations && !validationError && <p role="status">Cargando validaciones…</p>}
        {validations && (validations.length ? <ul>{validations.map(rule => <li key={rule.rule_code}>{rule.affected_rows > 0 ? <AlertTriangle size={17} /> : <CheckCircle2 size={17} />}<span>{rules[rule.rule_code] || rule.rule_code}</span><strong>{rule.affected_rows > 0 ? `${rule.affected_rows} excluidos` : 'Correcto'}</strong></li>)}</ul> : <p>No hay validaciones publicadas para esta ejecución.</p>)}
      </article>}
      <p className="etl-privacy">Este panel muestra el funcionamiento de la carga. Los análisis personales se consultan únicamente por su titular. Pulso de la comunidad publica resúmenes agregados para perfiles profesionales, con un mínimo de diez participantes y supresión de métricas con pocos contribuyentes.</p>
    </>}
  </section>
}
