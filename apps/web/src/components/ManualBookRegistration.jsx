import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiRequest } from '../api/client'
import { useAuth } from '../context/AuthContext'
import './ManualBookRegistration.css'

export default function ManualBookRegistration() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(null)
  const request = useRef(null)
  const [coverMode, setCoverMode] = useState('url')
  const [coverFile, setCoverFile] = useState(null)
  const [coverUrl, setCoverUrl] = useState('')
  const [preview, setPreview] = useState('')
  const [coverError, setCoverError] = useState('')
  const [previewFailed, setPreviewFailed] = useState(false)
  useEffect(() => {
    const url = coverMode === 'file' && coverFile ? URL.createObjectURL(coverFile) : ''
    setPreview(url); setPreviewFailed(false)
    return () => { if (url) URL.revokeObjectURL(url) }
  }, [coverMode, coverFile, coverUrl])
  const selectCover = event => {
    const file = event.target.files?.[0]
    request.current = null; setCoverError(''); setCoverFile(null)
    if (!file) return
    if (!['image/png', 'image/jpeg'].includes(file.type)) { setCoverError('Selecciona una imagen PNG o JPG.'); event.target.value = ''; return }
    if (file.size > 5 * 1024 * 1024) { setCoverError('La portada admite hasta 5 MB.'); event.target.value = ''; return }
    setCoverFile(file)
  }
  if (!['autor', 'editorial', 'admin'].includes(user?.role)) return null
  const submit = async event => {
    event.preventDefault()
    if (busy || coverError) return
    if (coverMode === 'file' && !coverFile) { setCoverError('Selecciona una imagen PNG o JPG.'); return }
    const values = Object.fromEntries(new FormData(event.currentTarget))
    const body = { title: values.title.trim(), isbn: values.isbn.trim(), authors: values.authors.split('\n').map(value => value.trim()).filter(Boolean),
      language: values.language, publisher_name: values.publisher_name.trim() || null, description: values.description.trim() || null,
      publication_date: values.publication_date || null, page_count: values.page_count ? Number(values.page_count) : null,
      cover_url: coverMode === 'url' ? coverUrl.trim() || null : null, reason: 'Registro manual de libro con ISBN declarado por su responsable' }
    const snapshot = JSON.stringify({ body, file: coverMode === 'file' && coverFile ? [coverFile.name, coverFile.size, coverFile.lastModified] : null })
    if (request.current?.snapshot !== snapshot) request.current = { snapshot, key: crypto.randomUUID() }
    setBusy(true); setError('')
    try {
      let payload = JSON.stringify(body)
      if (coverMode === 'file' && coverFile) { payload = new FormData(); payload.append('data', JSON.stringify(body)); payload.append('cover', coverFile) }
      setSaved(await apiRequest('/books/manual', { method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}`, 'Idempotency-Key': request.current.key }, body: payload }))
    } catch (cause) { setError(cause.status === 422 ? 'Revisa el ISBN, los autores, la fecha y los datos del formulario. El ISBN debe tener dígitos de control válidos.' : cause.message) } finally { setBusy(false) }
  }
  return <section className="manual-book-registration">
    <div className="manual-book-heading"><div><h2>¿Tu libro aún no está en el catálogo?</h2><p>Regístralo directamente en LibrIA con su ISBN. No necesita aparecer en Google Books.</p></div><button type="button" className="button" disabled={busy} onClick={() => setOpen(value => !value)} aria-expanded={open}>{open ? 'Cerrar registro' : 'Registrar libro en LibrIA'}</button></div>
    {open && (saved ? <div role="status"><h3>Libro registrado</h3><p>{saved.title} · ISBN {saved.isbn}</p><Link className="button primary" to={`/books/${saved.work_id}`}>Ver libro en el catálogo</Link></div> : <form onSubmit={submit}>
      <p>Busca primero por ISBN para evitar duplicados. Puedes completar los datos manualmente si no encuentras el libro.</p>
      <fieldset disabled={busy} className="manual-book-grid">
        <label>ISBN registrado *<input name="isbn" required minLength={10} maxLength={30} placeholder="ISBN-10 o ISBN-13" /><small>Comprobamos su estructura y dígitos; no certificamos su inscripción ante una agencia ISBN.</small></label>
        <label>Título *<input name="title" required maxLength={200} /></label>
        <label>Autores *<textarea name="authors" required maxLength={3000} rows={3} placeholder="Un nombre por línea" /></label>
        <label>Editorial<input name="publisher_name" maxLength={500} /></label>
        <label>Idioma de la edición<select name="language" defaultValue="es"><option value="es">Español</option></select></label>
        <label>Fecha de publicación<input name="publication_date" type="date" /></label>
        <label>Número de páginas<input name="page_count" type="number" min={1} max={100000} /></label>
        <fieldset className="manual-book-wide manual-cover-picker"><legend>Portada del libro</legend>
          <div className="manual-cover-options"><label><input type="radio" name="cover_mode" value="url" checked={coverMode === 'url'} onChange={() => { setCoverMode('url'); setCoverError('') }} /> Usar URL</label><label><input type="radio" name="cover_mode" value="file" checked={coverMode === 'file'} onChange={() => { setCoverMode('file'); setCoverError('') }} /> Subir imagen PNG o JPG</label></div>
          {coverMode === 'url' ? <label>URL de la portada<input name="cover_url" type="url" maxLength={3000} placeholder="https://..." value={coverUrl} onChange={event => setCoverUrl(event.target.value)} /></label> : <label>Imagen de portada<input type="file" accept="image/png,image/jpeg,.png,.jpg,.jpeg" required onChange={selectCover} /><small>PNG o JPG, hasta 5 MB. La imagen se guarda en LibrIA.</small>{coverFile && <small>{coverFile.name}</small>}</label>}
          {(preview || (coverMode === 'url' && /^https?:\/\//i.test(coverUrl))) && !previewFailed && <img className="manual-cover-preview" src={coverMode === 'file' ? preview : coverUrl} alt="Vista previa de la portada" onError={() => setPreviewFailed(true)} />}
          {previewFailed && <p role="status">No se pudo mostrar la vista previa. Revisa la imagen o la URL.</p>}
          {coverError && <p role="alert">{coverError}</p>}
        </fieldset>
        <label className="manual-book-wide">Sinopsis<textarea name="description" maxLength={30000} rows={4} /></label>
        <label className="manual-book-wide manual-book-confirm"><input type="checkbox" required /> Confirmo que el ISBN corresponde a esta edición y que los datos ingresados son correctos.</label>
        <button className="button primary" disabled={busy || Boolean(coverError)}>{busy ? 'Registrando…' : 'Guardar libro en LibrIA'}</button>
      </fieldset>{error && <p className="admin-message error" role="alert">{error}</p>}
    </form>)}
  </section>
}
