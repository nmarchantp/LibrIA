import { useId, useState } from 'react'
import './RegistrationPasswordFields.css'

function passwordStrength(password) {
  const variety = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^a-zA-Z0-9\s]/]
    .filter(pattern => pattern.test(password)).length
  if (password.length < 8 || variety < 2 || /^(.)\1+$/.test(password) || /^(password|contraseña|123456|qwerty)/i.test(password)) return 1
  return password.length >= 12 && variety >= 3 ? 3 : 2
}

export default function RegistrationPasswordFields({ disabled = false }) {
  const id = useId()
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const mismatch = confirmation.length > 0 && password !== confirmation
  const strength = password ? passwordStrength(password) : 0
  return <div className="registration-password-fields">
    <label htmlFor={`${id}-password`}>Contraseña
      <input id={`${id}-password`} name="password" type="password" autoComplete="new-password"
        minLength={8} maxLength={128} required disabled={disabled} value={password}
        onChange={event => setPassword(event.target.value)} placeholder="Al menos 8 caracteres"
        aria-describedby={`${id}-strength ${id}-help`} />
    </label>
    <div className="password-strength" data-strength={strength}>
      <div className="password-strength-bars" aria-hidden="true">{[1, 2, 3].map(level => <span key={level} className={strength >= level ? 'is-filled' : ''} />)}</div>
      <p id={`${id}-strength`} role="status">{strength ? `Seguridad estimada: ${['', 'Baja', 'Media', 'Alta'][strength]}` : 'Seguridad: ingresa una contraseña'}</p>
    </div>
    <p id={`${id}-help`} className="password-help">Usa al menos 8 caracteres. Para mayor seguridad, combina 12 o más caracteres con mayúsculas, minúsculas, números y símbolos.</p>
    <label htmlFor={`${id}-confirmation`}>Confirmar contraseña
      <input id={`${id}-confirmation`} name="password_confirmation" type="password"
        autoComplete="new-password" minLength={8} maxLength={128} required disabled={disabled}
        value={confirmation} onChange={event => setConfirmation(event.target.value)}
        placeholder="Vuelve a ingresar tu contraseña" aria-invalid={mismatch || undefined}
        aria-describedby={confirmation ? `${id}-match` : undefined} />
    </label>
    {confirmation && <p id={`${id}-match`} className={`password-match${mismatch ? ' is-mismatch' : ''}`} role="status">
      {mismatch ? 'Las contraseñas no coinciden.' : 'Las contraseñas coinciden.'}
    </p>}
  </div>
}
