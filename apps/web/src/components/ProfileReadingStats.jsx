import { BookCheck, BookOpen, Library, Bookmark } from 'lucide-react'

export default function ProfileReadingStats({ books = [], loading, loadError }) {
  const stats = [
    { label: 'Libros', value: books.length, Icon: Library },
    { label: 'Leyendo', value: books.filter(book => book.status === 'Leyendo').length, Icon: BookOpen },
    { label: 'Terminados', value: books.filter(book => book.status === 'Terminado').length, Icon: BookCheck },
    { label: 'Pendientes', value: books.filter(book => book.status === 'Pendiente').length, Icon: Bookmark },
  ]
  return <>
    <dl className="reader-profile-stats" aria-label="Estadísticas de tu biblioteca" aria-busy={loading}>
      {stats.map(({ label, value, Icon }) => <div className="reader-profile-stat" key={label}><span className="reader-profile-stat-icon"><Icon size={25} strokeWidth={1.5} aria-hidden="true" /></span><div><dt>{label}</dt><dd>{loading || loadError ? '—' : value}</dd></div></div>)}
    </dl>
    {loadError && <p className="reader-profile-stat-notice" role="status">Las estadísticas no están disponibles mientras no se pueda cargar la biblioteca.</p>}
  </>
}
