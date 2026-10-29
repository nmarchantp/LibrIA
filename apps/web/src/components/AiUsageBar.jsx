import { useEffect, useState } from 'react'
import { apiRequest } from '../api/client'
import { useAuth } from '../context/AuthContext'
import './AiUsageBar.css'

const number = value => new Intl.NumberFormat('es-CL').format(value)

export default function AiUsageBar() {
  const { user } = useAuth()
  const [state, setState] = useState({})
  useEffect(() => {
    if (!user) return
    let active = true
    const controller = new AbortController()
    setState({})
    async function load() {
      try {
        const data = await apiRequest('/analytics/me/free-usage', {
          headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` },
          signal: controller.signal,
        })
        if (active) setState({ data })
      } catch (error) {
        if (active && error.name !== 'AbortError') setState({ error: true })
      }
    }
    load()
    const timer = window.setInterval(load, 30000)
    window.addEventListener('focus', load)
    return () => { active = false; controller.abort(); window.clearInterval(timer); window.removeEventListener('focus', load) }
  }, [user])
  if (!user) return null
  const { data, error } = state
  return <aside className="ai-usage" aria-label="Uso personal de IA gratuita">
    <strong>Tu uso de IA gratuita</strong>
    {!data ? <p role="status">{error ? 'No se pudo consultar el consumo de IA.' : 'Consultando tu consumo…'}</p>
      : !data.configured ? <p>La cuota gratuita diaria aún no está configurada.</p>
        : <>
          <p>{number(data.used_tokens)} / {number(data.allocated_tokens)} tokens usados · {data.used_percent}%</p>
          <progress max="100" value={data.used_percent} aria-label="Porcentaje de tu cuota diaria consumida" />
          <p><strong>{number(data.remaining_tokens)} tokens disponibles</strong> · Tu cuota representa el 100%.</p>
          <small>{number(data.pool_tokens)} tokens diarios ÷ {number(data.active_users)} usuarios con sesión activa. Cuota compartida entre Recomendaciones, Libros y Mi análisis ADN; se recalcula al cambiar los usuarios activos. Se cuentan entrada y respuesta de IA.</small>
          <small>Renovación: {new Date(data.resets_at).toLocaleString('es-CL')} (tu hora local). {data.free_mode ? '' : 'El proveedor no está configurado en modo gratuito.'} Este indicador informa el consumo; no bloquea consultas.</small>
        </>}
    {data?.pending_reconciliation_calls > 0 && <small role="status">Hay {number(data.pending_reconciliation_calls)} consulta(s) cuyo consumo está pendiente de confirmar.</small>}
  </aside>
}
