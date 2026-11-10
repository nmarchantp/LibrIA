import { apiRequest } from '../api/client'

export const kindLabels = { publication: 'Publicación', review: 'Reseña', comment: 'Comentario' }
export const statusLabels = { pending_review: 'Pendiente de revisión', approved: 'Aprobado', rejected: 'Rechazado', pending: 'Pendiente', dismissed: 'Descartado', hidden: 'Ocultado', restored: 'Restituido', superseded: 'Sustituido', withdrawn: 'Retirado' }
export const reasonLabels = { discrimination: 'Discriminación', harassment: 'Acoso o insultos', threats: 'Amenazas', sexual_content: 'Contenido sexual inapropiado', spam: 'Spam', other: 'Otro' }
export const categoryLabels = { racism_xenophobia: 'Racismo o xenofobia', homophobia_transphobia: 'Homofobia o transfobia', misogyny_sexism: 'Misoginia o sexismo', hate_speech: 'Discurso de odio', harassment_insults: 'Acoso o insultos', threats: 'Amenazas', sexual_harassment: 'Acoso sexual', spam: 'Spam' }
export function moderationRequest(path, options = {}) {
  return apiRequest(path, { ...options, headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}`, ...options.headers } })
}
export function moderationError(error) {
  if (error.status === 403) return 'Ya no tienes autorización para realizar esta acción.'
  if (error.status === 404) return 'El contenido ya no está disponible o no tienes acceso.'
  if (error.status === 409) return 'El contenido cambió o ya fue resuelto. Actualiza y revísalo antes de continuar.'
  return error.message || 'No se pudo completar la solicitud.'
}
