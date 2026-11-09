import { Bell, BookOpen, CalendarDays, Heart, Sparkles } from 'lucide-react'

const notifications = [
  { icon: Heart, title: 'A Camila le gustó tu reseña', text: 'La sutileza del viento', time: 'Hace 12 min' },
  { icon: CalendarDays, title: 'Un evento comienza pronto', text: 'Feria del Libro de Santiago', time: 'Hace 2 h' },
  { icon: Sparkles, title: 'Tienes nuevas recomendaciones', text: 'Encontramos 5 libros compatibles contigo', time: 'Ayer' },
  { icon: BookOpen, title: 'Continúa tu lectura', text: 'Llevas un 64% de La vegetariana', time: 'Hace 2 días' },
]

export default function NotificationsPage() {
  return <section className="page-width page community-page">
    <span className="kicker">TU ACTIVIDAD</span><h1 className="page-title">Notificaciones</h1>
    <div className="notification-list">
      {notifications.map(({ icon: Icon, title, text, time }) => <article className="notification" key={title}>
        <span className="notification-icon"><Icon size={20} /></span><div><h2>{title}</h2><p>{text}</p></div><time>{time}</time>
      </article>)}
    </div>
    <p className="demo-notice"><Bell size={17} /> Actividad de demostración; las notificaciones reales requieren la API social.</p>
  </section>
}
