import { useEffect, useState } from 'react'
import { BookOpen, Layers3, Search, Plus, GitMerge, RefreshCw, X } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { adminCatalogRequest } from '../services/adminCatalogService'
import CatalogBookEditor from '../components/CatalogBookEditor'
import CatalogGroupingPanel from '../components/CatalogGroupingPanel'
import './AdminCatalogPage.css'

export default function AdminCatalogPage() {
  const { access } = useAuth()
  const [tab, setTab] = useState('books')
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [offset, setOffset] = useState(0)
  const [revision, setRevision] = useState(0)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState({})
  const [grouping, setGrouping] = useState([])
  const [editor, setEditor] = useState(null)
  const canManage = access?.catalog_manage ?? access?.catalog_merge
  useEffect(() => {
    if (!access?.catalog_preview) return
    const controller = new AbortController()
    setLoading(true); setError('')
    const params = new URLSearchParams({ q: search, filter_by: filter, offset, limit: 20 })
    adminCatalogRequest(`/inventory?${params}`, { signal: controller.signal }).then(setData).catch(cause => {
      if (cause.name !== 'AbortError') setError(cause.message)
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [access?.catalog_preview, search, filter, offset, revision])
  function select(work) {
    setSelected(current => {
      const next = { ...current }
      if (next[work.id]) delete next[work.id]
      else if (Object.keys(next).length < 2) next[work.id] = work
      return next
    })
  }
  function group(main, duplicate) {
    setEditor(null); setGrouping([duplicate, main]); setTab('grouping')
  }
  if (!access?.catalog_preview) return <p>El mantenedor de libros está deshabilitado para esta cuenta.</p>
  const picked = Object.values(selected)
  const total = data?.total || 0
  return <section className="admin-catalog catalog-maintainer">
    <header className="catalog-header"><div><span className="catalog-eyebrow">Administración · LibrIAverse</span><h1>Mantenedor de libros</h1><p>Corrige las fichas del catálogo, administra sus ediciones y reúne los registros de una misma obra.</p></div>
      {canManage && <button className="catalog-primary" onClick={() => setEditor('new')}><Plus size={17} />Nuevo libro</button>}</header>
    <nav className="catalog-main-tabs" aria-label="Administración de libros"><button aria-current={tab === 'books' ? 'page' : undefined} onClick={() => setTab('books')}><BookOpen size={17} />Libros y ediciones</button>
      <button aria-current={tab === 'grouping' ? 'page' : undefined} onClick={() => setTab('grouping')}><GitMerge size={17} />Agrupación e historial</button></nav>
    {tab === 'books' && <>
      <div className="catalog-statistics"><article><BookOpen size={19} /><strong>{data?.stats.works ?? '—'}</strong><span>Obras en LibrIAverse</span></article><article><Layers3 size={19} /><strong>{data?.stats.editions ?? '—'}</strong><span>Ediciones registradas</span></article><article><GitMerge size={19} /><strong>{data?.stats.possible_duplicates ?? '—'}</strong><span>Obras con posibles duplicados</span></article></div>
      <section className="catalog-panel catalog-inventory" aria-label="Catálogo de libros" aria-busy={loading}>
        <form className="catalog-inventory-search" onSubmit={event => { event.preventDefault(); setSearch(query.trim()); setOffset(0); setRevision(value => value + 1) }}>
          <label>Buscar en el catálogo<input type="search" maxLength={200} placeholder="Título, autor o ISBN" value={query} onChange={event => setQuery(event.target.value)} /></label><button className="catalog-primary"><Search size={17} />Buscar</button>
          <label>Mostrar<select value={filter} onChange={event => { setFilter(event.target.value); setOffset(0) }}><option value="all">Todos los libros</option><option value="duplicates">Posibles duplicados</option><option value="no_isbn">Con ISBN por completar</option><option value="no_cover">Sin portada</option></select></label>
          <button type="button" aria-label="Actualizar catálogo" onClick={() => setRevision(value => value + 1)} disabled={loading}><RefreshCw size={17} /></button>
        </form>
        {error && <p role="alert" className="catalog-error">{error}</p>}
        {!!picked.length && <div className="catalog-selection-bar" role="region" aria-label="Libros seleccionados para agrupar"><div><strong>{picked.length} de 2 libros seleccionados</strong>{picked.map(work => <span key={work.id}>{work.title}<button aria-label={`Quitar ${work.title}`} onClick={() => select(work)}><X size={13} /></button></span>)}</div><button className="catalog-primary" disabled={picked.length !== 2} onClick={() => group(picked[0], picked[1])}><GitMerge size={16} />Revisar agrupación</button><button onClick={() => setSelected({})}>Limpiar selección</button></div>}
        <p className="catalog-result-count" role="status">{loading ? 'Consultando catálogo…' : `${total} ${total === 1 ? 'libro encontrado' : 'libros encontrados'}. Selecciona dos para revisar su agrupación.`}</p>
        {!loading && !error && !data?.items.length && <div className="catalog-empty"><BookOpen size={30} /><h3>No encontramos libros</h3><p>Prueba con otra parte del título, el nombre del autor o un ISBN.</p></div>}
        <div className="catalog-table-wrap"><table className="catalog-inventory-table"><thead><tr><th><span className="sr-only">Selección</span></th><th>Libro</th><th>Ediciones</th><th>Revisión</th><th><span className="sr-only">Acciones</span></th></tr></thead><tbody>{data?.items.map(work => <tr key={work.id} className={selected[work.id] ? 'is-selected' : ''}>
          <td><input type="checkbox" aria-label={`Seleccionar ${work.title}`} checked={Boolean(selected[work.id])} disabled={!selected[work.id] && picked.length === 2} onChange={() => select(work)} /></td>
          <td><div className="catalog-inventory-book"><div className="catalog-edition-cover">{work.cover_url ? <img src={work.cover_url.replace(/^http:/, 'https:')} alt="" /> : <BookOpen size={22} />}</div><div><button className="catalog-title-button" onClick={() => setEditor(work.id)}>{work.title}</button><p>{work.authors.join(', ') || 'Autor por completar'}</p></div></div></td>
          <td><strong>{work.edition_count}</strong><small>{work.isbn_count} con ISBN</small></td><td>{work.duplicate_count ? <span className="catalog-duplicate-badge">{work.duplicate_count} posible{work.duplicate_count > 1 ? 's' : ''} duplicado{work.duplicate_count > 1 ? 's' : ''}</span> : <span className="catalog-help">Sin coincidencias pendientes</span>}</td>
          <td><button aria-label={`Gestionar ${work.title}`} onClick={() => setEditor(work.id)}>Gestionar</button></td></tr>)}</tbody></table></div>
        <footer className="catalog-pagination"><span>{total ? `${offset + 1}–${Math.min(offset + 20, total)} de ${total}` : '0 resultados'}</span><div><button disabled={loading || offset === 0} onClick={() => setOffset(value => Math.max(0, value - 20))}>Anterior</button><button disabled={loading || offset + 20 >= total} onClick={() => setOffset(value => value + 20)}>Siguiente</button></div></footer>
      </section>
    </>}
    {tab === 'grouping' && <CatalogGroupingPanel embedded key={grouping.map(work => work.id).join(':')} initialWorks={grouping} onComplete={() => { setRevision(value => value + 1); setSelected({}) }} />}
    {editor && <CatalogBookEditor key={editor} workId={editor} canEdit={Boolean(canManage)} onClose={() => setEditor(null)} onSaved={() => setRevision(value => value + 1)} onGroup={group} />}
  </section>
}
