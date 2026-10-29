import { useEffect, useRef, useState } from 'react'
import { BookOpen, Check, Plus, X } from 'lucide-react'
import { adminCatalogRequest, catalogChanged } from '../services/adminCatalogService'

const emptyWork = { title: '', authors: [], description: '', categories: [], series_title: '', volume_number: '', editions: [], changes: [], possible_duplicates: [] }
const sourceNames = { 'google-books': 'Google Books', 'open-library': 'Open Library', 'libria-feed': 'LibrIAverse', 'libria-editorial': 'Corrección administrativa' }
const actionNames = { work_create: 'Libro registrado', work_update: 'Ficha corregida', edition_create: 'Edición añadida', edition_update: 'Edición corregida', import: 'Libro importado' }

function WorkForm({ book, busy, save }) {
  const [draft, setDraft] = useState({ title: book.title, authors: book.authors.join('\n'), description: book.description || '',
    categories: book.categories.join(', '), series_title: book.series_title || '', volume_number: book.volume_number || '', reason: '' })
  const field = name => ({ value: draft[name], onChange: event => setDraft({ ...draft, [name]: event.target.value }) })
  return <form className="catalog-edit-form" onSubmit={event => { event.preventDefault(); save({ ...draft,
    authors: draft.authors.split('\n').map(value => value.trim()).filter(Boolean),
    categories: draft.categories.split(',').map(value => value.trim()).filter(Boolean) }) }}>
    <label>Título de la obra<input required maxLength={1000} {...field('title')} /></label>
    <label>Autores<textarea rows={2} placeholder="Un autor por línea" {...field('authors')} /><small>Escribe un autor por línea. Este nombre se mostrará en la ficha del libro.</small></label>
    <div className="catalog-form-grid"><label>Saga o colección<input maxLength={500} {...field('series_title')} /></label>
      <label>Número de volumen<input maxLength={50} placeholder="Ej.: 1" {...field('volume_number')} /></label></div>
    <label>Categorías<input placeholder="Fantasía, Romance" {...field('categories')} /><small>Separa las categorías con comas.</small></label>
    <label>Sinopsis<textarea rows={5} maxLength={30000} {...field('description')} /></label>
    <label>Motivo del cambio<textarea required minLength={3} maxLength={2000} rows={2} placeholder="Ej.: Corregir el nombre del autor según la ficha editorial" {...field('reason')} /></label>
    <div className="catalog-editor-actions"><button className="catalog-primary" disabled={busy}><Check size={16} />{busy ? 'Guardando…' : book.id ? 'Guardar ficha' : 'Crear libro'}</button></div>
  </form>
}

function EditionForm({ edition, book, busy, save, cancel }) {
  const [draft, setDraft] = useState({ title: edition?.title || book.title, isbn: edition?.isbn13 || edition?.isbn10 || '',
    language: edition?.language || 'es', publisher_name: edition?.publisher_name || '', publication_date: edition?.publication_date || '',
    page_count: edition?.page_count || '', cover_url: edition?.cover_url || '', description: edition?.description || '', format: edition?.format || '', reason: '' })
  const field = name => ({ value: draft[name], onChange: event => setDraft({ ...draft, [name]: event.target.value }) })
  return <form className="catalog-edit-form" onSubmit={event => { event.preventDefault(); save({ ...draft, page_count: draft.page_count === '' ? null : Number(draft.page_count) }, edition?.id) }}>
    <div className="catalog-section-title"><h3>{edition ? 'Editar edición' : 'Nueva edición'}</h3><button type="button" disabled={busy} onClick={cancel}>Volver a las ediciones</button></div>
    <label>Título de la edición<input required maxLength={1000} {...field('title')} /></label>
    <div className="catalog-form-grid"><label>ISBN<input maxLength={30} placeholder="ISBN-10 o ISBN-13" {...field('isbn')} /><small>Se valida el ISBN y se calcula su equivalencia cuando corresponde.</small></label>
      <label>Idioma<input required maxLength={20} placeholder="es" {...field('language')} /></label>
      <label>Editorial<input maxLength={500} {...field('publisher_name')} /></label>
      <label>Fecha de publicación<input maxLength={10} placeholder="2024, 2024-06 o 2024-06-20" {...field('publication_date')} /></label>
      <label>Número de páginas<input type="number" min={1} max={100000} {...field('page_count')} /></label>
      <label>Formato<input maxLength={100} placeholder="Tapa dura, bolsillo, digital…" {...field('format')} /></label></div>
    <label>URL de la portada<input type="url" maxLength={3000} placeholder="https://…" {...field('cover_url')} /></label>
    <label>Sinopsis de esta edición<textarea rows={3} maxLength={30000} {...field('description')} /></label>
    <label>Motivo del cambio<textarea required minLength={3} maxLength={2000} rows={2} {...field('reason')} /></label>
    <div className="catalog-editor-actions"><button className="catalog-primary" disabled={busy}><Check size={16} />{busy ? 'Guardando…' : edition ? 'Guardar edición' : 'Añadir edición'}</button></div>
  </form>
}

export default function CatalogBookEditor({ workId, onClose, onSaved, onGroup, canEdit }) {
  const dialog = useRef(null)
  const submission = useRef(null)
  const [book, setBook] = useState(null)
  const [tab, setTab] = useState('work')
  const [editingEdition, setEditingEdition] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  useEffect(() => {
    dialog.current.showModal()
    if (workId === 'new') { setBook(emptyWork); return }
    const controller = new AbortController()
    adminCatalogRequest(`/works/${workId}`, { signal: controller.signal }).then(setBook).catch(cause => {
      if (cause.name !== 'AbortError') setError(cause.message)
    })
    return () => controller.abort()
  }, [workId])
  async function save(body, editionId) {
    setBusy(true); setError(''); setMessage('')
    const edition = tab === 'editions'
    const path = !book.id ? '/works' : edition ? `/works/${book.id}/editions${editionId ? '/' + editionId : ''}` : `/works/${book.id}`
    const payload = { ...body, expected_version: book.version || null }
    const signature = JSON.stringify({ path, payload })
    if (submission.current?.signature !== signature) submission.current = { signature, key: crypto.randomUUID() }
    try {
      const next = await adminCatalogRequest(path, { body: payload, method: book.id && (!edition || editionId) ? 'PATCH' : 'POST', key: submission.current.key })
      setBook(next); setEditingEdition(null); setMessage('Cambios guardados en LibrIAverse.'); onSaved(next); catalogChanged()
    } catch (cause) { setError(cause.message) }
    finally { setBusy(false) }
  }
  return <dialog ref={dialog} className="catalog-book-dialog admin-catalog" aria-labelledby="catalog-editor-title" onCancel={event => { if (busy) event.preventDefault() }} onClose={onClose}>
    <header className="catalog-editor-header"><div><span className="catalog-eyebrow">{book?.id ? 'Gestionar libro' : 'Registro de libro'}</span><h2 id="catalog-editor-title">{book?.title || (workId === 'new' ? 'Nuevo libro' : 'Cargando libro…')}</h2>
      {book?.id && <p>{book.authors.join(', ') || 'Autor por completar'} · {book.edition_count} {book.edition_count === 1 ? 'edición' : 'ediciones'}</p>}</div>
      <button className="catalog-icon-button" type="button" aria-label="Cerrar editor" disabled={busy} onClick={() => dialog.current.close()}><X size={20} /></button></header>
    {error && <p role="alert" className="catalog-error">{error}</p>}{message && <p role="status" className="catalog-success">{message}</p>}
    {book && <>
      {book.id && <nav className="catalog-editor-tabs" aria-label="Secciones del libro">{[['work', 'Ficha'], ['editions', `Ediciones (${book.editions.length})`], ['duplicates', 'Posibles duplicados'], ['changes', 'Cambios recientes']].map(([id, title]) =>
        <button key={id} type="button" disabled={busy} aria-current={tab === id ? 'page' : undefined} onClick={() => { setTab(id); setEditingEdition(null); setError(''); setMessage('') }}>{title}</button>)}</nav>}
      {!canEdit && <p className="catalog-help">Tu acceso actual permite consultar el catálogo.</p>}
      <fieldset className="catalog-editor-body" disabled={busy || !canEdit}>
        {tab === 'work' && <WorkForm key={book.version || 'new'} book={book} busy={busy} save={save} />}
        {tab === 'editions' && (editingEdition ? <EditionForm key={editingEdition.id || 'new'} edition={editingEdition.id ? editingEdition : null} book={book} busy={busy} save={save} cancel={() => setEditingEdition(null)} /> : <>
          <div className="catalog-section-title"><div><h3>Ediciones de esta obra</h3><p>Cada ISBN identifica una publicación. Las lecturas conservan la edición que eligió cada usuario.</p></div><button className="catalog-primary" type="button" onClick={() => setEditingEdition({})}><Plus size={16} />Añadir edición</button></div>
          {!book.editions.length && <div className="catalog-empty"><BookOpen /><p>Este libro todavía no tiene ediciones. Añade la primera con sus datos editoriales.</p></div>}
          <ul className="catalog-managed-editions">{book.editions.map(edition => <li key={edition.id}><div className="catalog-edition-cover">{edition.cover_url ? <img src={edition.cover_url.replace(/^http:/, 'https:')} alt="" /> : <BookOpen size={22} />}</div><div className="catalog-edition-copy"><strong>{edition.title}</strong><p>ISBN: {edition.isbn13 || edition.isbn10 || 'Sin registrar'}</p><small>{[edition.publisher_name, edition.language?.toUpperCase(), edition.publication_date, edition.page_count ? `${edition.page_count} páginas` : null].filter(Boolean).join(' · ') || 'Datos por completar'}</small><small>{[...new Set(edition.sources.map(source => sourceNames[source.provider] || source.provider))].join(' · ')}</small></div><button type="button" onClick={() => setEditingEdition(edition)}>Editar edición</button></li>)}</ul>
        </>)}
      </fieldset>
      {tab === 'duplicates' && <section className="catalog-duplicates"><h3>Posibles duplicados</h3><p className="catalog-help">Coinciden el título normalizado y los autores. Revisa sus ediciones antes de agruparlos.</p>
        {!book.possible_duplicates.length && <p>No encontramos coincidencias exactas pendientes. También puedes seleccionar otro libro desde el catálogo.</p>}
        {book.possible_duplicates.map(other => <article key={other.id}><div><strong>{other.title}</strong><small>{other.authors.join(', ')} · {other.edition_count} ediciones</small></div><button disabled={busy} type="button" onClick={() => onGroup(book, other)}>Revisar agrupación</button></article>)}</section>}
      {tab === 'changes' && <section><h3>Cambios recientes</h3>{!book.changes.length && <p className="catalog-help">Aún no hay correcciones administrativas registradas para este libro.</p>}
        <ul className="catalog-change-log">{book.changes.map((change, index) => <li key={index}><strong>{actionNames[change.action] || 'Corrección del catálogo'}</strong><p>{change.reason}</p><small>{new Date(change.created_at).toLocaleString('es-CL', { timeZone: 'America/Santiago' })}</small></li>)}</ul></section>}
    </>}
  </dialog>
}
