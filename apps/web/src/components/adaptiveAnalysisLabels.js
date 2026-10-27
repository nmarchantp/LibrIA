// Shared by the book analysis and the reader DNA view.
export const formatAnalysisDate = value => new Intl.DateTimeFormat('es-CL', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Santiago' }).format(new Date(value))

export const sourceLabels = { reading: 'Lectura y cuaderno', review: 'Reseña y valoración propia', reflection: 'Reflexión de cierre', note: 'Nota propia', theory: 'Teoría propia', analysis: 'Experiencia individual', feedback: 'Tu corrección o confirmación' }
