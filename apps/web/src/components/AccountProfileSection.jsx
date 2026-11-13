import { useRef, useState } from 'react'
import { Check, Copy, Trash2, Upload } from 'lucide-react'
import { API_URL } from '../api/client'
import { accountRequest } from '../services/accountService'

const avatarTypes = ['image/jpeg', 'image/png', 'image/webp']
const biographyLimit = 70

export default function AccountProfileSection({ account, busy, run }) {
  const fileRef = useRef(null)
  const [name, setName] = useState(account.display_name)
  const [biography, setBiography] = useState(account.biography || '')
  const [copied, setCopied] = useState(false)
  const count = Array.from(biography).length
  const avatar = account.avatar_url && (account.avatar_url.startsWith('/api/') ? new URL(account.avatar_url, API_URL).href : account.avatar_url)
  const initials = account.display_name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('').toUpperCase()
  const upload = event => {
    const file = event.target.files[0]
    event.target.value = ''
    if (!file) return
    run(async () => {
      if (!avatarTypes.includes(file.type)) throw new Error('Elige una imagen JPEG, PNG o WebP.')
      if (file.size > 2 * 1024 * 1024) throw new Error('La fotografía no puede superar 2 MB.')
      const body = new FormData()
      body.append('file', file)
      return accountRequest('/me/avatar', 'PUT', body)
    }, 'Fotografía actualizada.')
  }
  const copy = async () => {
    try { await navigator.clipboard.writeText(account.username); setCopied(true); setTimeout(() => setCopied(false), 1800) }
    catch { /* The field stays selectable when the clipboard is unavailable. */ }
  }

  return <section className="account-panel" aria-labelledby="account-profile-heading">
    <header className="account-panel-header">
      <div><h2 id="account-profile-heading">Mi perfil</h2><p>Información visible en tu tarjeta comunitaria y reseñas.</p></div>
    </header>
    <div className="account-profile-grid">
      <div className="account-avatar-card">
        <div className="account-avatar">{avatar ? <img src={avatar} alt="Tu fotografía de perfil" /> : <span aria-hidden="true">{initials}</span>}</div>
        <strong>Fotografía de perfil</strong>
        <small>JPEG, PNG o WebP · Máximo 2 MB</small>
        <input ref={fileRef} className="account-file-input" type="file" accept={avatarTypes.join(',')} tabIndex={-1} aria-hidden="true" onChange={upload} />
        <button type="button" className="button account-button" disabled={busy} onClick={() => fileRef.current.click()}><Upload size={15} aria-hidden="true" />{avatar ? 'Cambiar fotografía' : 'Subir fotografía'}</button>
        <button type="button" className="button account-button ghost" disabled={busy || !avatar} onClick={() => run(() => accountRequest('/me/avatar', 'DELETE'), 'Fotografía retirada.')}><Trash2 size={15} aria-hidden="true" />Retirar fotografía</button>
      </div>
      <form className="account-form" onSubmit={event => { event.preventDefault(); run(() => accountRequest('/me', 'PATCH', { display_name: name, biography: biography || null }), 'Perfil actualizado.') }}>
        <fieldset disabled={busy}>
          <div className="account-field">
            <div className="account-field-label"><label htmlFor="account-username">Nombre de usuario (ID único)</label><small>Solo lectura</small></div>
            <div className="account-readonly">
              <input id="account-username" value={account.username} readOnly />
              <button type="button" onClick={copy} aria-label={copied ? 'Copiado' : 'Copiar nombre de usuario'} title={copied ? 'Copiado' : 'Copiar'}>{copied ? <Check size={15} aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}</button>
            </div>
          </div>
          <div className="account-field">
            <label htmlFor="account-display-name">Nombre para mostrar</label>
            <input id="account-display-name" value={name} onChange={event => setName(event.target.value)} minLength={2} maxLength={100} required />
          </div>
          <div className="account-field">
            <div className="account-field-label"><label htmlFor="account-biography">Biografía</label><small id="account-bio-count" className={count > biographyLimit ? 'is-over' : ''}>{count}/{biographyLimit} caracteres</small></div>
            <textarea id="account-biography" value={biography} onChange={event => setBiography(event.target.value)} placeholder="Una frase breve sobre tu vida lectora" aria-describedby="account-bio-count" aria-invalid={count > biographyLimit} rows={3} />
          </div>
          <button className="button primary account-submit" disabled={count > biographyLimit}>Guardar perfil</button>
        </fieldset>
      </form>
    </div>
  </section>
}
