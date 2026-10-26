import { useEffect, useState } from 'react'
import { apiRequest } from '../api/client'
import ReaderDna from './ReaderDna'
import BookExperience from './BookExperience'
import { useAuth } from '../context/AuthContext'

const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })
const errors = { context_capacity: 'Tu biblioteca supera la capacidad actual de contexto. No se ha publicado un análisis parcial como si fuera completo.', source_removed: 'La fuente ya no está disponible.', book_analysis_failed: 'Una experiencia individual no pudo analizarse. Reintenta desde la ficha de ese libro.', provider_timeout: 'Ollama superó el tiempo de espera. Puedes reintentar.' }

function PrivateAnalysis({ workId, scope }) {
  const isBook = scope === 'book'
  const base = isBook ? `/me/ai/books/${workId}` : '/me/ai/profile'
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [information, setInformation] = useState('')
  const [history, setHistory] = useState(null)
  const [historyBusy, setHistoryBusy] = useState(false)
  const [expiredDeadline, setExpiredDeadline] = useState(null)
  const deadline = data?.job?.deadline_at
  useEffect(() => {
    if(isBook || !deadline || !['pending','processing'].includes(data?.job?.status)) return
    const timer=setTimeout(() => setExpiredDeadline(deadline),Math.max(0,new Date(deadline).getTime()-Date.now()))
    return () => clearTimeout(timer)
  },[deadline,isBook,data?.job?.status])
  useEffect(() => {
    let active = true
    let timer
    async function load() {
      try {
        let result = await apiRequest(base, { headers: headers(), signal:AbortSignal.timeout(5000) })
        if (!active) return
        if (result.status !== 'awaiting_rating' && ((!result.job && !result.analysis) || result.needs_refresh)) {
          await apiRequest(`${base}/refresh`, { method: 'POST', headers: headers(), signal:AbortSignal.timeout(5000) })
          if (!active) return
          result = await apiRequest(base, { headers: headers(), signal:AbortSignal.timeout(5000) })
          if (!active) return
        }
        setData(result)
        setError('')
        setLoading(false)
        // Keep detecting updates made elsewhere, without submitting new jobs.
        timer = setTimeout(load, ['pending', 'processing'].includes(result.job?.status) ? 2500 : 15000)
      } catch {
        if (active) { setLoading(false); setError('No se pudo consultar tu análisis privado. Reintenta.'); timer = setTimeout(load, 15000) }
      }
    }
    load()
    return () => { active = false; clearTimeout(timer) }
  }, [base, refresh])

  async function requestRefresh() {
    setSubmitting(true); setError(''); setNotice('')
    try {
      const result = await apiRequest(`${base}/refresh`, { method: 'POST', headers: headers(), signal:AbortSignal.timeout(5000) })
      setData(current => ({ ...current, job: result.job || { status: result.status || 'pending' } }))
      setRefresh(value => value + 1)
    } catch (err) {
      if (['TimeoutError','AbortError'].includes(err.name)) {
        setNotice('La confirmación de la solicitud está tardando. Consultando si el análisis ya está en curso…')
        setRefresh(value => value + 1)
      } else setError('No se pudo solicitar el análisis. Puedes reintentar.')
    }
    finally { setSubmitting(false) }
  }

  async function sendFeedback(action) {
    setSubmitting(true); setError(''); setNotice('')
    try {
      await apiRequest('/me/ai/feedback', { method: 'POST', headers: headers(), body: JSON.stringify({ analysis_id: data.analysis.id, action, information }) })
      setInformation(''); setHistory(null)
      setData(current => ({ ...current, analysis: action === 'confirm' ? current.analysis : null, job: { status: 'pending' } }))
      setNotice('Tu respuesta quedó registrada y tendrá prioridad en la próxima interpretación.')
      setRefresh(value => value + 1)
    } catch { setError('No se pudo guardar tu respuesta. Actualiza el análisis antes de reintentar.') }
    finally { setSubmitting(false) }
  }

  async function loadHistory(before) {
    setHistoryBusy(true); setError('')
    try {
      const result = await apiRequest(`/me/ai/profile/history${before ? `?before=${before}` : ''}`, { headers: headers() })
      setHistory(current => before ? [...current, ...result.items] : result.items)
    } catch { setError('No se pudo consultar el historial privado.') }
    finally { setHistoryBusy(false) }
  }

  const analysis = data?.scope === scope ? data.analysis : null
  const content = analysis?.content
  const expired = !isBook && ['pending','processing'].includes(data?.job?.status) && Boolean(deadline) && expiredDeadline === deadline
  const working = submitting || (!expired && (loading || ['pending', 'processing'].includes(data?.job?.status)))
  const failed = expired || data?.job?.status === 'failed'
  const message = submitting ? 'Registrando solicitud…' : loading ? 'Consultando tu análisis privado…' : data?.job?.status === 'pending' ? 'Análisis pendiente. Se procesará automáticamente.' : data?.job?.status === 'processing' ? 'Ollama está interpretando tus experiencias de lectura…' : analysis ? 'Análisis completado · Tu versión está disponible' : ''
  const statusError = error || (expired || data?.job?.error_code === 'deadline_exceeded' ? 'No se pudo completar el ADN dentro de un minuto. Se conserva la última versión válida; puedes reintentar.' : failed ? errors[data.job.error_code] || 'El análisis no pudo completarse. Puedes reintentar; se conserva la última versión válida.' : '')
  if (!isBook) return <ReaderDna data={data} analysis={analysis} working={working} failed={failed} message={message} error={working ? '' : statusError} notice={notice} onRefresh={requestRefresh}
    submitting={submitting} information={information} setInformation={setInformation} onFeedback={sendFeedback} history={history} historyBusy={historyBusy} onLoadHistory={loadHistory} />
  return <BookExperience workId={workId} data={data} analysis={analysis} working={working} failed={failed} message={message} error={working ? '' : statusError} notice={notice} onRefresh={requestRefresh}
    submitting={submitting} information={information} setInformation={setInformation} onFeedback={sendFeedback} />
}

export default function AdaptiveAnalysis({ workId, scope = 'profile' }) {
  const { user } = useAuth()
  if (scope==='book' && !workId) return null
  return <PrivateAnalysis key={`${user?.id}:${scope}:${workId || 'profile'}`} scope={scope} workId={workId} />
}
