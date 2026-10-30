import { useCallback, useEffect, useRef, useState } from 'react'
import { apiRequest } from '../api/client'
import ReaderDna from './ReaderDna'
import AiUsageBar from './AiUsageBar'
import BookExperience from './BookExperience'
import { shouldPollBookAnalysis } from './bookAnalysisState'
import { useAuth } from '../context/AuthContext'

const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })
const errors = {
  monthly_budget_exhausted: 'El presupuesto mensual de IA está agotado.',
  provider_timeout: 'Gemini superó el tiempo de espera; el reintento automático permanece limitado.',
  provider_authentication: 'La credencial del proveedor no es válida.',
  provider_quota: 'La cuota del proveedor está temporalmente agotada.',
  provider_invalid_response: 'Gemini devolvió una respuesta incompleta. Puedes volver a intentarlo.',
  provider_error: 'Gemini rechazó la solicitud. Puedes volver a intentarlo.',
}

function PrivateAnalysis({ workId, scope, onWriteReview, evidenceRevision }) {
  const isBook = scope === 'book'
  const base = isBook ? `/me/ai/books/${workId}` : '/me/ai/profile'
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [information, setInformation] = useState('')
  const [history, setHistory] = useState(null)
  const [historyBusy, setHistoryBusy] = useState(false)
  const loadedBase = useRef(null)

  const load = useCallback(async (background = false) => {
    if (!background) setLoading(true)
    setError('')
    try { setData(await apiRequest(base, { headers: headers(), signal: AbortSignal.timeout(5000) })) }
    catch { setError('No se pudo consultar el resultado persistido.') }
    finally { if (!background) setLoading(false) }
  }, [base])

  const refresh = useCallback(async () => {
    setError(''); setNotice('')
    try {
      const endpoint = isBook ? `${base}/refresh` : '/me/ai/profile/refresh'
      await apiRequest(endpoint, { method: 'POST', headers: headers() })
      setData(await apiRequest(base, { headers: headers(), signal: AbortSignal.timeout(5000) }))
      setNotice(isBook ? 'Estado consultado. Las interpretaciones nuevas se preparan tras la actualización de datos automática o iniciada por un administrador.' : 'Solicitud registrada. Tu ADN lector aparecerá aquí cuando esté listo.')
    } catch (requestError) {
      setError(requestError.message || 'No se pudo solicitar el análisis.')
    } finally { setLoading(false) }
  }, [base, isBook])

  useEffect(() => {
    const background = loadedBase.current === base
    loadedBase.current = base
    load(background)
  }, [load, base, evidenceRevision])

  async function retryBook() {
    setSubmitting(true); setError('')
    try {
      setData(await apiRequest(`${base}/retry`, { method: 'POST', headers: headers() }))
      setNotice('El reintento quedó registrado para la próxima actualización de datos, automática o iniciada por un administrador.')
    } catch (cause) { setError(cause.message || 'No se pudo registrar el reintento.') }
    finally { setSubmitting(false) }
  }

  async function sendFeedback(action) {
    if (!data?.analysis?.id) return
    setSubmitting(true); setError(''); setNotice('')
    try {
      await apiRequest('/me/ai/feedback', { method: 'POST', headers: headers(), body: JSON.stringify({ analysis_id: data.analysis.id, action, information }) })
      setInformation(''); setHistory(null)
      if (action !== 'confirm') setData(current => ({ ...current, analysis: null }))
      setNotice('Tu respuesta quedó registrada. No se creará un segundo análisis para el mismo evento.')
    } catch { setError('No se pudo guardar tu respuesta. Consulta nuevamente el resultado antes de reintentar.') }
    finally { setSubmitting(false) }
  }

  async function loadHistory(before) {
    setHistoryBusy(true); setError('')
    try {
      const result = await apiRequest(`${base}/history${before ? `?before=${before}` : ''}`, { headers: headers() })
      setHistory(current => before ? [...current, ...result.items] : result.items)
    } catch { setError('No se pudo consultar el historial privado.') }
    finally { setHistoryBusy(false) }
  }

  const analysis = data?.scope === scope ? data.analysis : null
  const jobStatus = data?.job?.status || data?.status
  useEffect(() => {
    if (isBook ? !shouldPollBookAnalysis(data) : !['pending', 'processing'].includes(jobStatus)) return undefined
    const timer = window.setInterval(() => load(true), 2500)
    return () => window.clearInterval(timer)
  }, [jobStatus, load, isBook, data])
  const servicePaused = isBook && data?.generation_enabled === false && jobStatus === 'pending'
  const working = loading || (!servicePaused && ['pending', 'processing'].includes(jobStatus))
  const failed = ['failed', 'budget_exhausted'].includes(jobStatus)
  const scheduledAt = Date.parse(data?.job?.not_before)
  const scheduled = isBook && jobStatus === 'pending' && scheduledAt > Date.now()
  const minutes = scheduled ? Math.max(1, Math.ceil((scheduledAt - Date.now()) / 60000)) : 0
  const message = loading ? 'Consultando tu análisis guardado…'
    : jobStatus === 'pending' ? scheduled
      ? `El análisis podrá comenzar en aproximadamente ${minutes} ${minutes === 1 ? 'minuto' : 'minutos'}. Esta espera te permite completar tu valoración, reseña y notas; si las editas, puede extenderse. Si ya terminaste, pulsa «Analizar ahora».`
      : 'Tu análisis está en cola y comenzará cuando haya disponibilidad. No necesitas volver a solicitarlo. Esta página se actualizará automáticamente.'
    : jobStatus === 'processing' ? 'Gemini está preparando tu análisis. Puede tardar más de un minuto. Puedes salir y volver después; el resultado quedará guardado aquí.'
    : analysis ? 'Tu análisis guardado está disponible.'
    : data?.status === 'waiting_for_etl' ? 'Tus datos aún no están preparados para la IA. Un administrador debe ejecutar la actualización de datos; después podrás solicitar tu análisis.'
    : data?.status === 'insufficient_data' ? 'Para preparar tu ADN lector, termina un libro y valóralo con al menos 4 estrellas. Después de la próxima actualización de datos podrás solicitar el análisis.' : ''
  const statusError = error || (!isBook && failed ? errors[data?.job?.error_code] || 'No se pudo completar el análisis. Puedes volver a intentarlo.' : '')
  const shared = { data, analysis, working, failed, message, error: error || (working ? '' : statusError), notice,
    onRefresh: refresh, submitting, information, setInformation, onFeedback: sendFeedback,
    refreshDisabled: isBook ? loading : loading || jobStatus === 'processing' || (jobStatus === 'pending' && !scheduled),
    refreshLabel: isBook ? 'Actualizar estado' : scheduled ? 'Analizar ahora' : analysis ? 'Consultar análisis' : 'Solicitar análisis' }
  if (!isBook) return <ReaderDna {...shared} history={history} historyBusy={historyBusy} onLoadHistory={loadHistory} />
  return <BookExperience {...shared} workId={workId} onRetry={retryBook} onWriteReview={onWriteReview} history={history} historyBusy={historyBusy} onLoadHistory={loadHistory} />
}

export default function AdaptiveAnalysis({ workId, scope = 'profile', onWriteReview, evidenceRevision }) {
  const { user } = useAuth()
  if (scope === 'book' && !workId) return null
  return <><AiUsageBar /><PrivateAnalysis key={`${user?.id}:${scope}:${workId || 'profile'}`} scope={scope} workId={workId} onWriteReview={onWriteReview} evidenceRevision={evidenceRevision} /></>
}
