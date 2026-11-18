export function analysisErrorMessage(job) {
  if (job?.error_provider && job.error_provider !== 'gemini' && job?.error_code?.startsWith('provider_')) {
    return 'El intento anterior no se completó. El proveedor activo es Gemini; solicita una actualización del análisis.'
  }
  const provider = job?.error_provider === 'gemini' ? 'Gemini' : 'El proveedor de IA'
  const errors = {
    monthly_budget_exhausted: 'El presupuesto mensual de IA de LibrIA está agotado.',
    provider_timeout: `${provider} superó el tiempo de espera.`,
    provider_authentication: `La credencial de ${provider === 'El proveedor de IA' ? 'la API' : provider} no es válida.`,
    provider_quota: `${provider} rechazó la solicitud por un límite de cuota o de solicitudes.`,
    provider_invalid_response: `${provider} devolvió una respuesta incompleta o inválida.`,
    provider_error: `${provider} rechazó la solicitud.`,
    provider_server: `${provider} no estuvo disponible.`,
  }
  return errors[job?.error_code] || 'No se pudo completar el análisis. Puedes volver a consultar su estado.'
}
