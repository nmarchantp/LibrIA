import { useEffect, useState } from 'react'
import { BarChart3 } from 'lucide-react'
import { useLibrary } from '../context/LibraryContext'
import { profileService } from '../services/profileService'

const percentage = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 1 })

export default function MostReadGenresCard() {
  const { books, loading: libraryLoading, loadError } = useLibrary()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    if (libraryLoading) return
    setLoading(true); setError('')
    profileService.readingGenres().then(result => { if (active) { setData(result); setLoading(false) } })
      .catch(() => { if (active) { setError('No se pudieron cargar tus estadísticas.'); setLoading(false) } })
    return () => { active = false }
  }, [books, libraryLoading, attempt])
  return <section className="reader-personal-card reader-most-read" aria-busy={loading || libraryLoading}>
    <h2><BarChart3 size={19} aria-hidden="true" />Mis géneros más leídos</h2>
    <p className="reader-card-description">Basado en los libros que he terminado.</p>
    {loading || libraryLoading ? <p role="status">Calculando tus géneros leídos…</p> : error ? <><p role="alert">{error}</p><button className="reader-edit-button" type="button" onClick={() => setAttempt(value => value + 1)}>Reintentar</button></> : data?.status === 'ready' ? <>
      <ul className="reader-genre-ranking">{data.genres.map((genre, index) => <li key={genre.name}>
        <div><span>{genre.name}</span><strong>{percentage.format(genre.percentage)}%</strong></div>
        <progress className={`reader-genre-bar reader-genre-bar-${index + 1}`} value={genre.percentage} max="100" aria-label={`${genre.name}: ${percentage.format(genre.percentage)}%`} />
      </li>)}</ul>
      <details className="reader-genre-method"><summary>Cómo se calculan estos porcentajes</summary><div>
        <p className="reader-genre-explanation">{data.classified_books} {data.classified_books === 1 ? 'libro terminado' : 'libros terminados'} · {data.total_assignments} {data.total_assignments === 1 ? 'asignación de género' : 'asignaciones de género'}.</p>
        {data.unclassified_books > 0 && <p className="reader-genre-explanation">{data.unclassified_books} {data.unclassified_books === 1 ? 'libro sin géneros, excluido' : 'libros sin géneros, excluidos'}.</p>}
        <p className="reader-genre-explanation">Top 5 sobre todas las asignaciones. Los porcentajes redondeados pueden no sumar 100%.</p>
      </div></details>
    </> : <p className="reader-module-empty">{data?.status === 'no_finished_books' ? 'Cuando termines libros en tu biblioteca, aquí verás sus géneros más frecuentes.' : 'Tus libros terminados todavía no tienen géneros bibliográficos suficientes para calcular porcentajes.'}</p>}
    {loadError && <p className="reader-genre-explanation">La biblioteca no pudo actualizarse. Estas estadísticas se consultan directamente en la base de datos.</p>}
  </section>
}
