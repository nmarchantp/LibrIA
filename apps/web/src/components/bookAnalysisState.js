export const bookAnalysisMessages = {
  not_eligible: ['Tu aventura aún está en curso', 'Termina o abandona una lectura para descubrir su interpretación.'],
  requires_review: ['Tu historia aún guarda secretos', 'Escribe una reseña sobre tu aventura literaria para que nuestra lechuza pueda llevar tus palabras a los sabios.'],
  waiting_nightly_processing: ['¡Tu lechuza está lista para partir!', 'Tu reseña ya está guardada. Nuestra lechuza partirá tras la actualización de datos de medianoche, o antes si un administrador la ejecuta.'],
  queued: ['Tu lechuza se prepara para partir', 'Tu historia está preparada. Los sabios la interpretarán cuando puedan recibirla.'],
  processing: ['¡Tu lechuza ha partido!', 'Los sabios están interpretando tu experiencia de lectura. Cuando su respuesta esté lista, podrás descubrirla aquí.'],
  completed: ['¡Tu lechuza ha regresado!', 'Los sabios han descifrado tu experiencia literaria. Descubre qué revela tu aventura.'],
  update_pending: ['Tu historia tiene nuevos secretos', 'Tus palabras han cambiado. Prepararemos una nueva interpretación tras la próxima actualización de datos, automática o iniciada por un administrador. Mientras tanto, puedes seguir explorando el mensaje anterior de los sabios.'],
  update_processing: ['Una nueva lechuza está en camino', 'Los sabios están revisando los nuevos detalles de tu aventura. Tu interpretación anterior seguirá disponible mientras esperamos su respuesta.'],
  failed: ['La lechuza encontró una tormenta', 'No pudimos completar tu interpretación esta vez. Tu reseña está a salvo. Consulta el estado más adelante.'],
}

export function shouldPollBookAnalysis(data) {
  if (data?.generation_enabled === false && data?.job?.status !== 'processing') return false
  return ['queued', 'processing', 'update_processing'].includes(data?.status) ||
    (data?.status === 'update_pending' && data?.job?.status === 'pending')
}
