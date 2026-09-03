// Datos temporales para desarrollar la interfaz sin depender todavía del backend.
// Cuando exista FastAPI, este arreglo será reemplazado por una petición HTTP a la API.
export const books = [
  { id: 1, title: 'La vegetariana', author: 'Han Kang', year: 2007, status: 'Leyendo', progress: 64, color: '#173f35', accent: '#ffb65c', initial: 'V' },
  { id: 2, title: 'El infinito en un junco', author: 'Irene Vallejo', year: 2019, status: 'Leyendo', progress: 31, color: '#d76542', accent: '#f7dca8', initial: '∞' },
  { id: 3, title: 'Los detectives salvajes', author: 'Roberto Bolaño', year: 1998, status: 'Pendiente', progress: 0, color: '#e8c05c', accent: '#243d58', initial: 'D' },
  { id: 4, title: 'Distancia de rescate', author: 'Samanta Schweblin', year: 2014, status: 'Terminado', progress: 100, rating: 5, color: '#2e4778', accent: '#f38a69', initial: 'DR' },
]

// Distribución emocional simulada que alimenta las barras del panel "Mis patrones".
// Los porcentajes reales serán generados posteriormente por el proceso ETL.
export const emotions = [
  { name: 'Curiosidad', value: 38, color: '#f0a34a' },
  { name: 'Asombro', value: 27, color: '#db674c' },
  { name: 'Melancolía', value: 21, color: '#527c73' },
  { name: 'Calma', value: 14, color: '#b5c7a5' },
]
